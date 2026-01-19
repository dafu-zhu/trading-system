"""
MACD trading strategy using DataGateway.

Generates BUY/SELL/HOLD signals based on MACD crossovers.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from data_loader.features.calculator import FeatureCalculator, FeatureParams
from models import DataGateway, MarketDataPoint, Strategy, Timeframe


class MACDStrategy(Strategy):
    """
    MACD trading strategy.

    Generates signals based on MACD crossovers:
    - BUY: MACD crosses above signal line
    - SELL: MACD crosses below signal line
    - HOLD: No crossover
    """

    def __init__(
        self,
        gateway: DataGateway,
        timeframe: Timeframe = Timeframe.DAY_1,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        """
        Initialize MACD strategy.

        :param gateway: DataGateway for fetching bar data
        :param timeframe: Timeframe for bar data (default: daily)
        :param fast_period: Fast EMA period (default: 12)
        :param slow_period: Slow EMA period (default: 26)
        :param signal_period: Signal line EMA period (default: 9)
        """
        self._gateway = gateway
        self._timeframe = timeframe
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._signal_period = signal_period

        self._feature_params = FeatureParams(
            macd_fast=fast_period,
            macd_slow=slow_period,
            macd_signal=signal_period,
        )

        # Cache for loaded data
        self._data_cache: dict[str, pd.DataFrame] = {}

    def get_data(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Load and prepare data with MACD features.

        :param symbol: Stock symbol
        :param start: Start datetime (defaults to 1 year ago)
        :param end: End datetime (defaults to now)
        :return: DataFrame with OHLCV data, MACD indicators, and signals
        """
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)

        # Fetch bars from gateway
        bars = self._gateway.fetch_bars(symbol, self._timeframe, start, end)

        if not bars:
            return pd.DataFrame()

        # Calculate MACD features
        df = FeatureCalculator.calculate(bars, ['macd'], self._feature_params)

        # Generate trading signals
        df = FeatureCalculator.generate_macd_signals(df)

        # Cache for tick-by-tick lookups
        self._data_cache[symbol] = df

        return df

    def generate_signals(self, tick: MarketDataPoint) -> list:
        """
        Generate signals for a single tick using pre-calculated MACD data.

        :param tick: Market data point with timestamp, symbol, and price
        :return: List with single signal dict
        """
        if tick.symbol not in self._data_cache:
            self.get_data(tick.symbol)

        df = self._data_cache.get(tick.symbol)
        if df is None or df.empty:
            return [self._make_signal('HOLD', tick)]

        # Find exact timestamp match or closest prior
        if tick.timestamp in df.index:
            signal = str(df.loc[tick.timestamp, 'signal'])
            return [self._make_signal(signal, tick)]

        prior = df[df.index <= tick.timestamp]
        if prior.empty:
            return [self._make_signal('HOLD', tick)]

        signal = str(prior.iloc[-1]['signal'])
        return [self._make_signal(signal, tick)]

    def generate_signals_batch(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """
        Generate signals for all bars in a date range.

        :param symbol: Stock symbol
        :param start: Start datetime
        :param end: End datetime
        :return: DataFrame with OHLCV, MACD, and signal columns
        """
        return self.get_data(symbol, start, end)

    @staticmethod
    def _make_signal(action: str, tick: MarketDataPoint) -> dict:
        """Create signal dict from action and tick."""
        return {
            'action': action,
            'timestamp': tick.timestamp,
            'symbol': tick.symbol,
            'price': tick.price,
        }

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear cached data.

        :param symbol: Symbol to clear (None clears all)
        """
        if symbol:
            self._data_cache.pop(symbol, None)
        else:
            self._data_cache.clear()

    @property
    def gateway(self) -> DataGateway:
        """Get the data gateway."""
        return self._gateway

    @property
    def timeframe(self) -> Timeframe:
        """Get the timeframe."""
        return self._timeframe
