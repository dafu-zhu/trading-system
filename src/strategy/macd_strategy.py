from models import Strategy, MarketDataPoint
import pandas as pd
from pathlib import Path
from data_loader.preprocessing import Preprocessor


class MACDStrategy(Strategy):
    """
    MACD trading strategy using pre-calculated MACD values from preprocessing.

    Expects DataFrame with 'macd', 'macd_signal', and 'macd_histogram' columns.
    """

    def __init__(
            self,
            data_path: Path,
            fast_period: int = 12,
            slow_period: int = 26,
            signal_period: int = 9
    ):
        self.data_path = data_path
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.df = None

    def get_data(self, symbol: str) -> pd.DataFrame:
        """Load and prepare data with MACD features."""
        file_path = self.data_path / f"{symbol}.csv"
        self.df = (
            Preprocessor(file_path)
            .load()
            .clean()
            .add_features(
                features=['macd'],
                macd_fast_period=self.fast_period,
                macd_slow_period=self.slow_period,
                macd_signal_period=self.signal_period
            )
            .clean()
            .get_data
        )
        # Generate signals
        self.df = self.generate_signals_from_dataframe(self.df)
        return self.df

    def generate_signals(self, tick: MarketDataPoint) -> list:
        """Generate signals for a single tick using pre-calculated MACD data."""
        if self.df is None:
            self.get_data(tick.symbol)

        # Find the row matching the tick's timestamp
        try:
            row = self.df.loc[tick.timestamp]

            return [{
                'action': str(row['signal']),
                'timestamp': tick.timestamp,
                'symbol': tick.symbol,
                'price': tick.price,
            }]
        except KeyError:
            # Timestamp not found in data
            return [{
                'action': 'HOLD',
                'timestamp': tick.timestamp,
                'symbol': tick.symbol,
                'price': tick.price,
            }]

    @staticmethod
    def generate_signals_from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals from DataFrame with pre-calculated MACD values.

        Args:
            df: DataFrame with 'macd', 'macd_signal', 'macd_histogram' columns

        Returns:
            DataFrame with added 'signal' column ('BUY', 'SELL', 'HOLD')
        """
        required_cols = ['macd', 'macd_signal', 'macd_histogram']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}. Use .add_features(features=['macd'])")

        df_result = df.copy()
        df_result['signal'] = 'HOLD'

        # Bullish crossover: MACD crosses above signal
        bullish = (
            (df_result['macd'].shift(1) <= df_result['macd_signal'].shift(1)) &
            (df_result['macd'] > df_result['macd_signal'])
        )
        df_result.loc[bullish, 'signal'] = 'BUY'

        # Bearish crossover: MACD crosses below signal
        bearish = (
            (df_result['macd'].shift(1) >= df_result['macd_signal'].shift(1)) &
            (df_result['macd'] < df_result['macd_signal'])
        )
        df_result.loc[bearish, 'signal'] = 'SELL'

        return df_result


if __name__ == '__main__':
    from data_loader import YF_DATA_PATH

    print("=" * 70)
    print("MACD Strategy Example")
    print("=" * 70)

    # Initialize strategy
    strategy = MACDStrategy(
        data_path=YF_DATA_PATH,
        fast_period=12,
        slow_period=26,
        signal_period=9
    )

    # Example 1: Load data and generate signals
    print("\n[Example 1] Loading AAPL data with MACD signals...")
    df = strategy.get_data(symbol='AAPL')

    print(f"\nDataFrame Info:")
    print(f"  Shape: {df.shape}")
    print(f"  Date range: {df.index[0]} to {df.index[-1]}")

    # Analyze signals
    buy_count = (df['signal'] == 'BUY').sum()
    sell_count = (df['signal'] == 'SELL').sum()
    hold_count = (df['signal'] == 'HOLD').sum()

    print(f"\nSignal Distribution:")
    print(f"  Total: {len(df):,}")
    print(f"  BUY:   {buy_count:,} ({buy_count/len(df)*100:.2f}%)")
    print(f"  SELL:  {sell_count:,} ({sell_count/len(df)*100:.2f}%)")
    print(f"  HOLD:  {hold_count:,} ({hold_count/len(df)*100:.2f}%)")

    # Show buy signals
    buy_signals = df[df['signal'] == 'BUY']
    if len(buy_signals) > 0:
        print("\n" + "=" * 70)
        print("First 3 BUY Signals:")
        print("=" * 70)
        print(buy_signals[['Adj Close', 'macd', 'macd_signal', 'macd_histogram', 'signal']].head(3))

    # Show sell signals
    sell_signals = df[df['signal'] == 'SELL']
    if len(sell_signals) > 0:
        print("\n" + "=" * 70)
        print("First 3 SELL Signals:")
        print("=" * 70)
        print(sell_signals[['Adj Close', 'macd', 'macd_signal', 'macd_histogram', 'signal']].head(3))

    # Example 2: Using generate_signals() with ticks
    print("\n" + "=" * 70)
    print("[Example 2] Using generate_signals() with individual ticks")
    print("=" * 70)

    if len(buy_signals) > 0:
        timestamp = buy_signals.index[0]
        price = buy_signals.iloc[0]['Adj Close']

        tick = MarketDataPoint(timestamp=timestamp, symbol='AAPL', price=price)
        signal = strategy.generate_signals(tick)[0]

        print(f"\nBUY Signal at {timestamp}:")
        print(f"  Action: {signal['action']}")
        print(f"  Price: ${signal['price']:.2f}")

    if len(sell_signals) > 0:
        timestamp = sell_signals.index[0]
        price = sell_signals.iloc[0]['Adj Close']

        tick = MarketDataPoint(timestamp=timestamp, symbol='AAPL', price=price)
        signal = strategy.generate_signals(tick)[0]

        print(f"\nSELL Signal at {timestamp}:")
        print(f"  Action: {signal['action']}")
        print(f"  Price: ${signal['price']:.2f}")

    # Show recent data
    print("\n" + "=" * 70)
    print("Last 10 Data Points:")
    print("=" * 70)
    print(df[['Adj Close', 'macd', 'macd_signal', 'macd_histogram', 'signal']].tail(10))
