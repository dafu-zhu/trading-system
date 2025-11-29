from pathlib import Path
from typing import Iterator, Optional, List, Union
import pandas as pd
import logging

from models import MarketDataPoint, Gateway
from data.preprocessing import Preprocessor
from logger.logger import setup_logging

logger = logging.getLogger("src.gateway")
setup_logging()


class HistoricalGateway(Gateway):
    """
    Simulate market data gateway using historical data
    """
    def __init__(
        self,
        data_path: Path,
        symbols: Union[str, List[str]],
        price_column: str = 'Adj Close',
        load_features: bool = False,
        feature_list: Optional[List[str]] = None,
        **feature_kwargs
    ):
        self.data_path = Path(data_path)
        self.symbols = [symbols] if isinstance(symbols, str) else symbols
        self.price_column = price_column
        self.load_features = load_features
        self.feature_list = feature_list or []
        self.feature_kwargs = feature_kwargs

        # Data storage
        self.data: dict[str, pd.DataFrame] = {}
        self.merged_data: Optional[pd.DataFrame] = None
        self.current_index: int = 0
        self.connected: bool = False

        logger.info(f"Initialized HistoricalGateway for symbols: {self.symbols}")

    def connect(self) -> bool:
        """
        Load historical dataframe
        :return: True if successfully loaded, False otherwise

        Features:
        - Load historical data by 'Preprocessor' class, calculate basic features if needed
        - Merge data from different symbols into one, in chronological order
        """
        try:
            logger.info(f"Loading historical data for {len(self.symbols)} symbol(s)...")

            for symbol in self.symbols:
                file_path = self.data_path / f"{symbol}.csv"

                if not file_path.exists():
                    logger.error(f"Data file not found: {file_path}")
                    return False

                # Load and clean data
                preprocessor = Preprocessor(file_path).load().clean()

                # Optionally add features
                if self.load_features and self.feature_list:
                    preprocessor.add_features(
                        features=self.feature_list,
                        **self.feature_kwargs
                    ).clean()

                df = preprocessor.get_data
                df['symbol'] = symbol  # Add symbol column
                self.data[symbol] = df

                logger.info(f"Loaded {len(df)} rows for {symbol}")

            # Merge data from all symbols and sort by timestamp
            if len(self.symbols) == 1:
                self.merged_data = self.data[self.symbols[0]]
            else:
                self.merged_data = pd.concat(self.data.values(), axis=0)
                self.merged_data = self.merged_data.sort_index()

            logger.info(f"Total data points: {len(self.merged_data)}")
            self.current_index = 0
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect and clear data."""
        self.data.clear()
        self.merged_data = None
        self.current_index = 0
        self.connected = False
        logger.info("Gateway disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if gateway is connected."""
        return self.connected

    def stream_data(self) -> Iterator[MarketDataPoint]:
        """
        Simulate real time market data feed using generator
        :return: MarketDataPoint as single tick
        """
        if not self.connected or self.merged_data is None:
            raise RuntimeError("Gateway not connected. Call connect() first.")

        logger.info(f"Starting data stream from index {self.current_index}")

        for idx in range(self.current_index, len(self.merged_data)):
            row = self.merged_data.iloc[idx]
            timestamp = self.merged_data.index[idx]

            tick = MarketDataPoint(
                timestamp=timestamp,
                symbol=row['symbol'],
                price=float(row[self.price_column])
            )

            self.current_index = idx + 1
            yield tick

        logger.info("Data stream complete")

    def get_current_tick(self) -> Optional[MarketDataPoint]:
        # Edge case: no data
        if not self.connected or self.merged_data is None:
            return None

        # Edge case: run to the end of data
        if self.current_index >= len(self.merged_data):
            return None

        row = self.merged_data.iloc[self.current_index]
        timestamp = self.merged_data.index[self.current_index]

        return MarketDataPoint(
            timestamp=timestamp,
            symbol=row['symbol'],
            price=float(row[self.price_column])
        )

    def move_on(self) -> Optional[MarketDataPoint]:
        """
        Integrate get current data and increase index
        :return: current tick
        """
        tick = self.get_current_tick()
        if tick is not None:
            self.current_index += 1
        return tick

    def reset(self) -> None:
        """Reset stream to beginning."""
        self.current_index = 0
        logger.info("Gateway stream reset to beginning")

    def seek(self, index: int) -> None:
        """
        Jump to specified timestamp
        :param index: time
        :return: None
        """
        if not self.connected or self.merged_data is None:
            raise RuntimeError("Gateway not connected")

        if index < 0 or index >= len(self.merged_data):
            raise ValueError(f"Index {index} out of range [0, {len(self.merged_data)})")

        self.current_index = index
        logger.info(f"Gateway stream seeked to index {index}")

    def get_data_slice(self, start_idx: int, end_idx: int) -> pd.DataFrame:
        """
        Slice from data stream source (historical dataframe)
        :return: sliced dataframe
        """
        if start_idx > end_idx:
            raise ValueError(f"Start must be smaller then end, got {start_idx} > {end_idx}")

        if not self.connected or self.merged_data is None:
            raise RuntimeError("Gateway not connected")

        return self.merged_data.iloc[start_idx:end_idx].copy()

    def get_full_data(self) -> pd.DataFrame:
        """
        Return the complete data stream source
        """
        if not self.connected or self.merged_data is None:
            raise RuntimeError("Gateway not connected")

        return self.merged_data.copy()

    def __len__(self) -> int:
        """Return total number of data points."""
        if self.merged_data is None:
            return 0
        return len(self.merged_data)

    def __repr__(self) -> str:
        status = "connected" if self.connected else "disconnected"
        return (f"HistoricalGateway(symbols={self.symbols}, "
                f"status={status}, "
                f"position={self.current_index}/{len(self)})")


if __name__ == '__main__':
    from data.preprocessing import YF_DATA_PATH

    print("=" * 70)
    print("Historical Gateway Example")
    print("=" * 70)

    # Example 1: Single symbol streaming
    print("\n[Example 1] Streaming single symbol (AAPL)")
    print("-" * 70)

    gateway = HistoricalGateway(
        data_path=YF_DATA_PATH,
        symbols='AAPL',
        price_column='Adj Close'
    )

    # Connect to load data
    if gateway.connect():
        print(f" Connected: {gateway}")
        print(f"  Total data points: {len(gateway)}")

        # Stream first 10 ticks
        print("\nFirst 10 ticks:")
        tick_count = 0
        for tick in gateway.stream_data():
            print(f"  {tick.timestamp} | {tick.symbol} | ${tick.price:.2f}")
            tick_count += 1
            if tick_count >= 10:
                break

        # Get current position
        print(f"\nCurrent position: {gateway.current_index}/{len(gateway)}")

        # Reset and get first tick
        gateway.reset()
        first_tick = gateway.move_on()
        print(f"\nAfter reset, first tick: {first_tick.timestamp} | ${first_tick.price:.2f}")

        gateway.disconnect()

    # Example 2: Multiple symbols with features
    print("\n" + "=" * 70)
    print("[Example 2] Streaming multiple symbols with MACD features")
    print("-" * 70)

    gateway_multi = HistoricalGateway(
        data_path=YF_DATA_PATH,
        symbols=['AAPL', 'MSFT'],
        price_column='Adj Close',
        load_features=True,
        feature_list=['macd'],
        macd_fast_period=12,
        macd_slow_period=26,
        macd_signal_period=9
    )

    if gateway_multi.connect():
        print(f" Connected: {gateway_multi}")

        # Show data from both symbols
        print("\nFirst 5 ticks from merged stream:")
        for i, tick in enumerate(gateway_multi.stream_data()):
            print(f"  {tick.timestamp} | {tick.symbol:5s} | ${tick.price:.2f}")
            if i >= 4:
                break

        # Get data slice
        print("\nData slice [0:3]:")
        slice_df = gateway_multi.get_data_slice(0, 3)
        print(slice_df[['symbol', 'Adj Close', 'macd', 'macd_signal']].to_string())

        gateway_multi.disconnect()

    print("\n" + "=" * 70)
    print("Example Complete!")
    print("=" * 70)
