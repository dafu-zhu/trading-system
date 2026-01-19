"""
Alpaca Data Gateway implementation.

Provides historical and real-time market data via the Alpaca API
with optional SQLite caching.
"""

import os
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Iterator

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame as AlpacaTimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest
from alpaca.common.exceptions import APIError

from models import DataGateway, Bar, Timeframe, MarketCalendarDay
from data_loader.storage import BarStorage

logger = logging.getLogger(__name__)


class AlpacaDataGateway(DataGateway):
    """
    Data gateway implementation for Alpaca API.

    Fetches historical bars and market calendar data. Supports
    optional local SQLite caching for faster repeated access.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        use_cache: bool = True,
        storage: Optional[BarStorage] = None,
    ):
        """
        Initialize Alpaca data gateway.

        :param api_key: Alpaca API key (defaults to ALPACA_API_KEY env var)
        :param api_secret: Alpaca API secret (defaults to ALPACA_API_SECRET env var)
        :param use_cache: Whether to cache data in SQLite
        :param storage: Optional custom BarStorage instance
        """
        self._api_key = api_key or os.getenv("ALPACA_API_KEY")
        self._api_secret = api_secret or os.getenv("ALPACA_API_SECRET")

        if not self._api_key or not self._api_secret:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and "
                "ALPACA_API_SECRET environment variables or pass them directly."
            )

        self._data_client: Optional[StockHistoricalDataClient] = None
        self._trading_client: Optional[TradingClient] = None
        self._connected = False
        self._use_cache = use_cache
        self._storage = storage if storage else BarStorage() if use_cache else None

    def connect(self) -> bool:
        """Connect to Alpaca data API."""
        try:
            self._data_client = StockHistoricalDataClient(
                api_key=self._api_key,
                secret_key=self._api_secret,
            )
            # Also connect trading client for calendar access
            self._trading_client = TradingClient(
                api_key=self._api_key,
                secret_key=self._api_secret,
                paper=True,
            )
            self._connected = True
            logger.info("Connected to Alpaca data API")
            return True
        except APIError as e:
            logger.error("Failed to connect to Alpaca: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Alpaca data API."""
        self._data_client = None
        self._trading_client = None
        self._connected = False
        logger.info("Disconnected from Alpaca data API")

    def is_connected(self) -> bool:
        """Check if connected to Alpaca."""
        return self._connected and self._data_client is not None

    def _ensure_connected(self) -> None:
        """Raise error if not connected."""
        if not self.is_connected():
            raise RuntimeError("Not connected to Alpaca. Call connect() first.")

    def _to_alpaca_timeframe(self, timeframe: Timeframe) -> AlpacaTimeFrame:
        """Convert internal Timeframe to Alpaca TimeFrame."""
        mapping = {
            Timeframe.MIN_1: AlpacaTimeFrame(1, TimeFrameUnit.Minute),
            Timeframe.MIN_5: AlpacaTimeFrame(5, TimeFrameUnit.Minute),
            Timeframe.MIN_15: AlpacaTimeFrame(15, TimeFrameUnit.Minute),
            Timeframe.MIN_30: AlpacaTimeFrame(30, TimeFrameUnit.Minute),
            Timeframe.HOUR_1: AlpacaTimeFrame(1, TimeFrameUnit.Hour),
            Timeframe.HOUR_4: AlpacaTimeFrame(4, TimeFrameUnit.Hour),
            Timeframe.DAY_1: AlpacaTimeFrame(1, TimeFrameUnit.Day),
            Timeframe.WEEK_1: AlpacaTimeFrame(1, TimeFrameUnit.Week),
            Timeframe.MONTH_1: AlpacaTimeFrame(1, TimeFrameUnit.Month),
        }
        return mapping[timeframe]

    def _alpaca_bar_to_bar(self, symbol: str, alpaca_bar, timeframe: Timeframe) -> Bar:
        """Convert Alpaca bar to internal Bar."""
        return Bar(
            symbol=symbol,
            timestamp=alpaca_bar.timestamp.replace(tzinfo=None),  # Store as naive UTC
            timeframe=timeframe,
            open=float(alpaca_bar.open),
            high=float(alpaca_bar.high),
            low=float(alpaca_bar.low),
            close=float(alpaca_bar.close),
            volume=int(alpaca_bar.volume),
            vwap=float(alpaca_bar.vwap) if hasattr(alpaca_bar, 'vwap') and alpaca_bar.vwap else None,
            trade_count=int(alpaca_bar.trade_count) if hasattr(alpaca_bar, 'trade_count') and alpaca_bar.trade_count else None,
        )

    def fetch_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """
        Fetch historical bars for a symbol.

        If caching is enabled, checks cache first and only fetches
        missing data from Alpaca.
        """
        self._ensure_connected()

        # Check cache first
        if self._use_cache and self._storage:
            cached_bars = self._storage.get_bars(symbol, timeframe, start, end)
            if cached_bars:
                logger.debug(
                    "Found %d cached bars for %s %s",
                    len(cached_bars), symbol, timeframe.value
                )
                return cached_bars

        # Fetch from Alpaca
        bars = self._fetch_from_alpaca(symbol, timeframe, start, end)

        # Cache the results
        if self._use_cache and self._storage and bars:
            self._storage.save_bars(bars)
            logger.debug("Cached %d bars for %s", len(bars), symbol)

        return bars

    def _fetch_from_alpaca(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """Fetch bars directly from Alpaca API."""
        alpaca_tf = self._to_alpaca_timeframe(timeframe)

        # Ensure timezone-aware datetimes for Alpaca
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=alpaca_tf,
            start=start,
            end=end,
        )

        try:
            response = self._data_client.get_stock_bars(request)
            bars = []

            # Access data via .data attribute (BarSet object)
            data = response.data if hasattr(response, 'data') else response
            if symbol in data:
                for alpaca_bar in data[symbol]:
                    bars.append(self._alpaca_bar_to_bar(symbol, alpaca_bar, timeframe))

            logger.info(
                "Fetched %d bars for %s from %s to %s",
                len(bars), symbol, start.date(), end.date()
            )
            return bars

        except APIError as e:
            logger.error("Failed to fetch bars for %s: %s", symbol, e)
            return []

    def fetch_bars_bulk(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> dict[str, list[Bar]]:
        """
        Fetch bars for multiple symbols at once.

        :param symbols: List of stock symbols
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :return: Dictionary mapping symbols to their bars
        """
        self._ensure_connected()

        alpaca_tf = self._to_alpaca_timeframe(timeframe)

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=alpaca_tf,
            start=start,
            end=end,
        )

        try:
            response = self._data_client.get_stock_bars(request)
            result = {}

            # Access data via .data attribute (BarSet object)
            data = response.data if hasattr(response, 'data') else response
            for symbol in symbols:
                bars = []
                if symbol in data:
                    for alpaca_bar in data[symbol]:
                        bars.append(self._alpaca_bar_to_bar(symbol, alpaca_bar, timeframe))
                result[symbol] = bars

                # Cache each symbol's bars
                if self._use_cache and self._storage and bars:
                    self._storage.save_bars(bars)

            total_bars = sum(len(bars) for bars in result.values())
            logger.info("Fetched %d total bars for %d symbols", total_bars, len(symbols))
            return result

        except APIError as e:
            logger.error("Failed to fetch bulk bars: %s", e)
            return {symbol: [] for symbol in symbols}

    def stream_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Iterator[Bar]:
        """
        Stream bars one at a time for backtesting.

        Uses cached data if available, otherwise fetches from Alpaca.
        """
        self._ensure_connected()

        # Try cache first
        if self._use_cache and self._storage:
            cached_bars = self._storage.get_bars(symbol, timeframe, start, end)
            if cached_bars:
                logger.debug("Streaming %d cached bars for %s", len(cached_bars), symbol)
                for bar in cached_bars:
                    yield bar
                return

        # Fetch and stream
        bars = self._fetch_from_alpaca(symbol, timeframe, start, end)

        # Cache for future use
        if self._use_cache and self._storage and bars:
            self._storage.save_bars(bars)

        for bar in bars:
            yield bar

    def get_market_calendar(
        self,
        start: date,
        end: date,
    ) -> list[MarketCalendarDay]:
        """Get market calendar for a date range."""
        self._ensure_connected()

        try:
            request = GetCalendarRequest(start=start, end=end)
            calendar = self._trading_client.get_calendar(request)

            result = []
            for day in calendar:
                # Handle both datetime objects and string times
                if isinstance(day.open, datetime):
                    open_time = day.open
                    close_time = day.close
                else:
                    open_time = datetime.combine(
                        day.date,
                        datetime.strptime(day.open, "%H:%M").time(),
                    )
                    close_time = datetime.combine(
                        day.date,
                        datetime.strptime(day.close, "%H:%M").time(),
                    )

                # Check for early close (before 16:00)
                early_close = close_time.hour < 16

                result.append(MarketCalendarDay(
                    date=day.date,
                    open_time=open_time,
                    close_time=close_time,
                    is_open=True,
                    early_close=early_close,
                ))

            logger.debug("Retrieved calendar for %d trading days", len(result))
            return result

        except APIError as e:
            logger.error("Failed to get market calendar: %s", e)
            return []

    def get_latest_bar(self, symbol: str, timeframe: Timeframe) -> Optional[Bar]:
        """Get the most recent bar for a symbol."""
        self._ensure_connected()

        # For latest bar, fetch last few days to ensure we get data
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)

        bars = self.fetch_bars(symbol, timeframe, start, end)
        return bars[-1] if bars else None

    def get_storage(self) -> Optional[BarStorage]:
        """Get the underlying storage instance."""
        return self._storage

    def prefetch_data(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        chunk_days: int = 365,
    ) -> dict[str, int]:
        """
        Prefetch and cache data for multiple symbols.

        Fetches data in chunks to avoid API limits.

        :param symbols: List of stock symbols
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :param chunk_days: Days per chunk (default 365)
        :return: Dictionary mapping symbols to bar counts
        """
        self._ensure_connected()

        result = {symbol: 0 for symbol in symbols}
        current_start = start

        while current_start < end:
            chunk_end = min(current_start + timedelta(days=chunk_days), end)

            logger.info(
                "Fetching chunk: %s to %s for %d symbols",
                current_start.date(), chunk_end.date(), len(symbols)
            )

            bars_by_symbol = self.fetch_bars_bulk(symbols, timeframe, current_start, chunk_end)

            for symbol, bars in bars_by_symbol.items():
                result[symbol] += len(bars)

            current_start = chunk_end

        return result
