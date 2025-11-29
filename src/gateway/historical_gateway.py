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
    Gateway for streaming historical market data from CSV files.

    This gateway reads cleaned CSV files and streams them row-by-row
    to simulate real-time market data feed for backtesting.

    Features:
        - Reads cleaned CSV files from preprocessing
        - Streams data incrementally (row-by-row)
        - Supports single or multiple symbols
        - Maintains current position in data stream
        - Can reset and replay data
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
        """
        Initialize historical gateway.

        Args:
            data_path: Path to directory containing CSV files
            symbols: Single symbol or list of symbols to stream
            price_column: Column name to use as price
            load_features: Whether to load technical features
            feature_list: List of features to calculate if load_features=True
            **feature_kwargs: Additional arguments for feature calculation
        """
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
        Load historical data from CSV files.

        Returns:
            bool: True if data loaded successfully
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

    def is_connected(self) -> bool:
        """Check if gateway is connected."""
        return self.connected

    def stream_data(self) -> Iterator[MarketDataPoint]:
        """
        Stream market data points sequentially.

        Yields:
            MarketDataPoint: Individual market data ticks

        Raises:
            RuntimeError: If gateway is not connected
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
        """
        Get the current market data point without advancing the stream.

        Returns:
            Optional[MarketDataPoint]: Current tick or None if at end
        """
        if not self.connected or self.merged_data is None:
            return None

        if self.current_index >= len(self.merged_data):
            return None

        row = self.merged_data.iloc[self.current_index]
        timestamp = self.merged_data.index[self.current_index]

        return MarketDataPoint(
            timestamp=timestamp,
            symbol=row['symbol'],
            price=float(row[self.price_column])
        )

    def get_next_tick(self) -> Optional[MarketDataPoint]:
        """
        Get the next market data point and advance the stream.

        Returns:
            Optional[MarketDataPoint]: Next tick or None if at end
        """
        tick = self.get_current_tick()
        if tick is not None:
            self.current_index += 1
        return tick

    def has_more_data(self) -> bool:
        """
        Check if more data is available in the stream.

        Returns:
            bool: True if more data available
        """
        if not self.connected or self.merged_data is None:
            return False
        return self.current_index < len(self.merged_data)

    def reset(self) -> None:
        """Reset stream to beginning."""
        self.current_index = 0
        logger.info("Gateway stream reset to beginning")

    def seek(self, index: int) -> None:
        """
        Seek to specific position in stream.

        Args:
            index: Position to seek to
        """
        if not self.connected or self.merged_data is None:
            raise RuntimeError("Gateway not connected")

        if index < 0 or index >= len(self.merged_data):
            raise ValueError(f"Index {index} out of range [0, {len(self.merged_data)})")

        self.current_index = index
        logger.info(f"Gateway stream seeked to index {index}")

    def get_data_slice(self, start_idx: int, end_idx: int) -> pd.DataFrame:
        """
        Get a slice of the data without affecting stream position.

        Args:
            start_idx: Start index (inclusive)
            end_idx: End index (exclusive)

        Returns:
            DataFrame: Slice of data
        """
        if not self.connected or self.merged_data is None:
            raise RuntimeError("Gateway not connected")

        return self.merged_data.iloc[start_idx:end_idx].copy()

    def get_full_data(self) -> pd.DataFrame:
        """
        Get full dataset (useful for analysis after backtest).

        Returns:
            DataFrame: Complete historical data
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
        first_tick = gateway.get_next_tick()
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
