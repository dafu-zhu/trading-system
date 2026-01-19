"""
Feature calculator for bar data.

Calculates technical indicators from Bar objects without CSV dependencies.
"""

import pandas as pd
import numpy as np
from typing import Optional
from dataclasses import dataclass

from models import Bar


@dataclass
class FeatureParams:
    """Parameters for feature calculation."""
    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    # RSI
    rsi_window: int = 14
    # Moving averages
    ma_windows: tuple[int, ...] = (5, 10, 20, 50, 200)
    # Bollinger Bands
    bb_window: int = 20
    bb_std: float = 2.0
    # ATR
    atr_window: int = 14


class FeatureCalculator:
    """
    Calculate technical indicators from bar data.

    Works with list[Bar] objects from DataGateway, converting to DataFrame
    for calculation and returning enriched DataFrame.
    """

    @staticmethod
    def bars_to_dataframe(bars: list[Bar]) -> pd.DataFrame:
        """
        Convert list of Bar objects to pandas DataFrame.

        :param bars: List of Bar objects
        :return: DataFrame with OHLCV data, indexed by timestamp
        """
        if not bars:
            return pd.DataFrame()

        data = {
            'open': [b.open for b in bars],
            'high': [b.high for b in bars],
            'low': [b.low for b in bars],
            'close': [b.close for b in bars],
            'volume': [b.volume for b in bars],
            'symbol': [b.symbol for b in bars],
        }

        # Add optional fields if present
        if any(b.vwap is not None for b in bars):
            data['vwap'] = [b.vwap for b in bars]
        if any(b.trade_count is not None for b in bars):
            data['trade_count'] = [b.trade_count for b in bars]

        df = pd.DataFrame(data, index=[b.timestamp for b in bars])
        df.index.name = 'timestamp'
        return df.sort_index()

    @classmethod
    def calculate_all(
        cls,
        bars: list[Bar],
        params: Optional[FeatureParams] = None,
    ) -> pd.DataFrame:
        """
        Calculate all available features.

        :param bars: List of Bar objects
        :param params: Feature parameters (uses defaults if None)
        :return: DataFrame with all features
        """
        if params is None:
            params = FeatureParams()

        df = cls.bars_to_dataframe(bars)
        if df.empty:
            return df

        cls.add_macd(df, params.macd_fast, params.macd_slow, params.macd_signal)
        cls.add_rsi(df, params.rsi_window)
        cls.add_moving_averages(df, params.ma_windows)
        cls.add_bollinger_bands(df, params.bb_window, params.bb_std)
        cls.add_atr(df, params.atr_window)
        cls.add_returns(df)

        return df

    @classmethod
    def calculate(
        cls,
        bars: list[Bar],
        features: list[str],
        params: Optional[FeatureParams] = None,
    ) -> pd.DataFrame:
        """
        Calculate specified features.

        :param bars: List of Bar objects
        :param features: List of feature names ('macd', 'rsi', 'ma', 'bollinger', 'atr', 'returns')
        :param params: Feature parameters (uses defaults if None)
        :return: DataFrame with requested features
        """
        if params is None:
            params = FeatureParams()

        df = cls.bars_to_dataframe(bars)
        if df.empty:
            return df

        for feature in features:
            feature_lower = feature.lower()
            if feature_lower == 'macd':
                cls.add_macd(df, params.macd_fast, params.macd_slow, params.macd_signal)
            elif feature_lower == 'rsi':
                cls.add_rsi(df, params.rsi_window)
            elif feature_lower in ('ma', 'moving_average', 'moving_averages'):
                cls.add_moving_averages(df, params.ma_windows)
            elif feature_lower in ('bollinger', 'bb', 'bollinger_bands'):
                cls.add_bollinger_bands(df, params.bb_window, params.bb_std)
            elif feature_lower == 'atr':
                cls.add_atr(df, params.atr_window)
            elif feature_lower == 'returns':
                cls.add_returns(df)
            else:
                raise ValueError(f"Unknown feature: {feature}")

        return df

    @staticmethod
    def add_macd(
        df: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> None:
        """
        Add MACD (Moving Average Convergence Divergence) to DataFrame.

        Adds columns: macd, macd_signal, macd_histogram
        """
        exp_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        exp_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
        df['macd'] = exp_fast - exp_slow
        df['macd_signal'] = df['macd'].ewm(span=signal_period, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

    @staticmethod
    def add_rsi(df: pd.DataFrame, window: int = 14) -> None:
        """
        Add RSI (Relative Strength Index) to DataFrame.

        Adds column: rsi
        """
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

    @staticmethod
    def add_moving_averages(
        df: pd.DataFrame,
        windows: tuple[int, ...] = (5, 10, 20, 50, 200),
    ) -> None:
        """
        Add simple and exponential moving averages to DataFrame.

        Adds columns: sma_{window}, ema_{window} for each window
        """
        for window in windows:
            if len(df) >= window:
                df[f'sma_{window}'] = df['close'].rolling(window=window).mean()
                df[f'ema_{window}'] = df['close'].ewm(span=window, adjust=False).mean()

    @staticmethod
    def add_bollinger_bands(
        df: pd.DataFrame,
        window: int = 20,
        num_std: float = 2.0,
    ) -> None:
        """
        Add Bollinger Bands to DataFrame.

        Adds columns: bb_middle, bb_upper, bb_lower, bb_width, bb_position
        """
        df['bb_middle'] = df['close'].rolling(window=window).mean()
        rolling_std = df['close'].rolling(window=window).std()
        df['bb_upper'] = df['bb_middle'] + (rolling_std * num_std)
        df['bb_lower'] = df['bb_middle'] - (rolling_std * num_std)
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    @staticmethod
    def add_atr(df: pd.DataFrame, window: int = 14) -> None:
        """
        Add ATR (Average True Range) to DataFrame.

        Adds column: atr
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=window).mean()

    @staticmethod
    def add_returns(df: pd.DataFrame) -> None:
        """
        Add returns to DataFrame.

        Adds columns: returns, log_returns
        """
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

    @staticmethod
    def generate_macd_signals(df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals from MACD crossovers.

        Requires 'macd' and 'macd_signal' columns.
        Adds column: signal ('BUY', 'SELL', 'HOLD')

        :param df: DataFrame with MACD columns
        :return: DataFrame with added 'signal' column
        """
        required = ['macd', 'macd_signal']
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}. Call add_macd() first.")

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
