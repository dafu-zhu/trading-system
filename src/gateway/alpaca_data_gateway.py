"""
Alpaca Data Gateway implementation.

Provides historical and real-time market data via the Alpaca API
with optional SQLite caching and WebSocket streaming.
"""

import os
import logging
import threading
import time
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Iterator, Callable

from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame as AlpacaTimeFrame, TimeFrameUnit
from alpaca.data.live import StockDataStream, CryptoDataStream
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest
from alpaca.common.exceptions import APIError

from models import DataGateway, Bar, Timeframe, MarketCalendarDay, MarketDataPoint
from data_loader.storage import BarStorage
from config.trading_config import AssetType, DataType, SymbolConfig

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
        self._crypto_data_client: Optional[CryptoHistoricalDataClient] = None
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
            self._crypto_data_client = CryptoHistoricalDataClient(
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
        self._crypto_data_client = None
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

    def _ensure_utc(self, dt: datetime) -> datetime:
        """Ensure datetime is timezone-aware (UTC)."""
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

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
            vwap=float(alpaca_bar.vwap) if getattr(alpaca_bar, "vwap", None) else None,
            trade_count=int(alpaca_bar.trade_count)
            if getattr(alpaca_bar, "trade_count", None)
            else None,
        )

    def fetch_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        asset_class: Optional[AssetType] = None,
    ) -> list[Bar]:
        """
        Fetch historical bars for a symbol.

        Args:
            symbol: Trading symbol
            timeframe: Bar timeframe
            start: Start datetime
            end: End datetime
            asset_class: Asset type (STOCK or CRYPTO). If None, inferred from symbol.

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
                    len(cached_bars),
                    symbol,
                    timeframe.value,
                )
                return cached_bars

        # Fetch from Alpaca
        bars = self._fetch_from_alpaca(symbol, timeframe, start, end, asset_class)

        # Cache the results
        if self._use_cache and self._storage and bars:
            self._storage.save_bars(bars)
            logger.debug("Cached %d bars for %s", len(bars), symbol)

        return bars

    def _infer_asset_class(self, symbol: str) -> AssetType:
        """Infer asset class from symbol format. Crypto symbols contain '/'."""
        return AssetType.CRYPTO if "/" in symbol else AssetType.STOCK

    def _fetch_from_alpaca(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        asset_class: Optional[AssetType] = None,
    ) -> list[Bar]:
        """
        Fetch bars directly from Alpaca API.

        Args:
            symbol: Trading symbol
            timeframe: Bar timeframe
            start: Start datetime
            end: End datetime
            asset_class: Asset type (STOCK or CRYPTO). If None, inferred from symbol.
        """
        alpaca_tf = self._to_alpaca_timeframe(timeframe)
        start = self._ensure_utc(start)
        end = self._ensure_utc(end)

        # Resolve asset class
        resolved_asset_class = asset_class if asset_class else self._infer_asset_class(symbol)

        try:
            if resolved_asset_class == AssetType.CRYPTO:
                request = CryptoBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=alpaca_tf,
                    start=start,
                    end=end,
                )
                response = self._crypto_data_client.get_crypto_bars(request)
            else:
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=alpaca_tf,
                    start=start,
                    end=end,
                )
                response = self._data_client.get_stock_bars(request)

            data = response.data if hasattr(response, "data") else response
            bars = [
                self._alpaca_bar_to_bar(symbol, alpaca_bar, timeframe)
                for alpaca_bar in data.get(symbol, [])
            ]

            logger.info(
                "Fetched %d %s bars for %s from %s to %s",
                len(bars),
                resolved_asset_class.value,
                symbol,
                start.date(),
                end.date(),
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
        start = self._ensure_utc(start)
        end = self._ensure_utc(end)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=alpaca_tf,
            start=start,
            end=end,
        )

        try:
            response = self._data_client.get_stock_bars(request)
            data = response.data if hasattr(response, "data") else response
            result = {}

            for symbol in symbols:
                bars = [
                    self._alpaca_bar_to_bar(symbol, alpaca_bar, timeframe)
                    for alpaca_bar in data.get(symbol, [])
                ]
                result[symbol] = bars

                if self._use_cache and self._storage and bars:
                    self._storage.save_bars(bars)

            total_bars = sum(len(bars) for bars in result.values())
            logger.info(
                "Fetched %d total bars for %d symbols", total_bars, len(symbols)
            )
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
                logger.debug(
                    "Streaming %d cached bars for %s", len(cached_bars), symbol
                )
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

                result.append(
                    MarketCalendarDay(
                        date=day.date,
                        open_time=open_time,
                        close_time=close_time,
                        is_open=True,
                        early_close=early_close,
                    )
                )

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
                current_start.date(),
                chunk_end.date(),
                len(symbols),
            )

            bars_by_symbol = self.fetch_bars_bulk(
                symbols, timeframe, current_start, chunk_end
            )

            for symbol, bars in bars_by_symbol.items():
                result[symbol] += len(bars)

            current_start = chunk_end

        return result

    # ==================== WebSocket Streaming ====================

    def _init_streaming(self) -> None:
        """Initialize streaming components if not already done."""
        if not hasattr(self, "_stock_stream"):
            self._stock_stream: Optional[StockDataStream] = None
            self._crypto_stream: Optional[CryptoDataStream] = None
            self._stream_callback: Optional[Callable[[MarketDataPoint], None]] = None
            self._stream_thread: Optional[threading.Thread] = None
            self._is_streaming = False
            self._stop_streaming_flag = False
            self._subscribed_symbols: set[str] = set()
            self._symbol_configs: dict[str, SymbolConfig] = {}

    def _create_stock_stream(self) -> StockDataStream:
        """Create and return a StockDataStream instance."""
        return StockDataStream(
            api_key=self._api_key,
            secret_key=self._api_secret,
            feed=DataFeed.IEX,  # IEX for paper trading
        )

    def _create_crypto_stream(self) -> CryptoDataStream:
        """Create and return a CryptoDataStream instance."""
        return CryptoDataStream(
            api_key=self._api_key,
            secret_key=self._api_secret,
        )

    async def _handle_trade(self, trade) -> None:
        """Handle incoming trade data from WebSocket."""
        try:
            logger.debug("Received trade: %s @ %.4f", trade.symbol, float(trade.price))

            if self._stream_callback is None:
                logger.warning("No callback set for trade data")
                return

            tick = MarketDataPoint(
                timestamp=trade.timestamp.replace(tzinfo=None),
                symbol=trade.symbol,
                price=float(trade.price),
                volume=float(trade.size),
            )
            self._stream_callback(tick)
        except Exception as e:
            logger.exception("Error handling trade: %s", e)

    async def _handle_quote(self, quote) -> None:
        """Handle incoming quote data from WebSocket."""
        if self._stream_callback is None:
            return

        mid_price = (float(quote.bid_price) + float(quote.ask_price)) / 2
        tick = MarketDataPoint(
            timestamp=quote.timestamp.replace(tzinfo=None),
            symbol=quote.symbol,
            price=mid_price,
            volume=0.0,
            bid_price=float(quote.bid_price),
            ask_price=float(quote.ask_price),
        )
        self._stream_callback(tick)

    async def _handle_bar(self, bar) -> None:
        """Handle incoming bar data from WebSocket."""
        if self._stream_callback is None:
            return

        tick = MarketDataPoint(
            timestamp=bar.timestamp.replace(tzinfo=None),
            symbol=bar.symbol,
            price=float(bar.close),
            volume=float(bar.volume),
        )
        self._stream_callback(tick)

    def _run_stream(
        self,
        stream: StockDataStream | CryptoDataStream,
        max_retries: int = 5,
    ) -> None:
        """
        Run the WebSocket stream with reconnection logic.

        Args:
            stream: The data stream to run
            max_retries: Maximum reconnection attempts
        """
        retry_count = 0
        base_delay = 1.0

        while not self._stop_streaming_flag and retry_count < max_retries:
            try:
                logger.info("Starting WebSocket stream...")
                stream.run()
                # If run() returns normally, we're done
                break
            except Exception as e:
                retry_count += 1
                delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
                logger.warning(
                    "Stream error (attempt %d/%d): %s. Retrying in %.1fs",
                    retry_count,
                    max_retries,
                    e,
                    delay,
                )
                if not self._stop_streaming_flag:
                    time.sleep(delay)

        if retry_count >= max_retries:
            logger.error("Max retries exceeded for WebSocket stream")

        self._is_streaming = False
        logger.info("WebSocket stream stopped")

    def stream_realtime(
        self,
        symbols: list[str] | list[SymbolConfig],
        callback: Callable[[MarketDataPoint], None],
        data_type: DataType = DataType.TRADES,
        default_asset_type: AssetType = AssetType.STOCK,
    ) -> None:
        """
        Start streaming real-time market data.

        This is a BLOCKING call. Use start_streaming() for non-blocking.

        Args:
            symbols: List of symbols or SymbolConfig objects
            callback: Function called with each MarketDataPoint
            data_type: Type of data to stream (trades, quotes, bars)
            default_asset_type: Default asset type for simple symbol strings
        """
        self._init_streaming()

        # Parse symbol configs
        stock_symbols = []
        crypto_symbols = []

        for sym in symbols:
            if isinstance(sym, SymbolConfig):
                self._symbol_configs[sym.symbol] = sym
                if sym.asset_type == AssetType.CRYPTO:
                    crypto_symbols.append(sym.symbol)
                else:
                    stock_symbols.append(sym.symbol)
            else:
                # Simple string - use default
                if default_asset_type == AssetType.CRYPTO:
                    crypto_symbols.append(sym)
                else:
                    stock_symbols.append(sym)

        self._stream_callback = callback
        self._subscribed_symbols = set(stock_symbols + crypto_symbols)
        self._is_streaming = True
        self._stop_streaming_flag = False

        # Subscribe to data based on type
        if stock_symbols:
            self._stock_stream = self._create_stock_stream()
            if data_type == DataType.TRADES:
                self._stock_stream.subscribe_trades(self._handle_trade, *stock_symbols)
            elif data_type == DataType.QUOTES:
                self._stock_stream.subscribe_quotes(self._handle_quote, *stock_symbols)
            elif data_type == DataType.BARS:
                self._stock_stream.subscribe_bars(self._handle_bar, *stock_symbols)

            logger.info(
                "Subscribed to %s for stocks: %s",
                data_type.value,
                stock_symbols,
            )

        if crypto_symbols:
            self._crypto_stream = self._create_crypto_stream()
            if data_type == DataType.TRADES:
                self._crypto_stream.subscribe_trades(self._handle_trade, *crypto_symbols)
            elif data_type == DataType.QUOTES:
                self._crypto_stream.subscribe_quotes(self._handle_quote, *crypto_symbols)
            elif data_type == DataType.BARS:
                self._crypto_stream.subscribe_bars(self._handle_bar, *crypto_symbols)

            logger.info(
                "Subscribed to %s for crypto: %s",
                data_type.value,
                crypto_symbols,
            )
            logger.info("Waiting for crypto market data (this may take a moment)...")

        # Run the streams (blocking)
        # If both stock and crypto, run stock in main thread
        if stock_symbols and self._stock_stream:
            if crypto_symbols and self._crypto_stream:
                # Start crypto in background thread
                crypto_thread = threading.Thread(
                    target=self._run_stream,
                    args=(self._crypto_stream,),
                    daemon=True,
                )
                crypto_thread.start()
            self._run_stream(self._stock_stream)
        elif crypto_symbols and self._crypto_stream:
            self._run_stream(self._crypto_stream)

    def start_streaming(
        self,
        symbols: list[str] | list[SymbolConfig],
        callback: Callable[[MarketDataPoint], None],
        data_type: DataType = DataType.TRADES,
        default_asset_type: AssetType = AssetType.STOCK,
    ) -> None:
        """
        Start streaming in a background thread (non-blocking).

        Args:
            symbols: List of symbols or SymbolConfig objects
            callback: Function called with each MarketDataPoint
            data_type: Type of data to stream
            default_asset_type: Default asset type for simple strings
        """
        self._init_streaming()

        if self._is_streaming:
            logger.warning("Already streaming. Stop first before restarting.")
            return

        self._stream_thread = threading.Thread(
            target=self.stream_realtime,
            args=(symbols, callback, data_type, default_asset_type),
            daemon=True,
        )
        self._stream_thread.start()
        logger.info("Started streaming in background thread")

    def stop_streaming(self) -> None:
        """Stop all active streams."""
        self._init_streaming()

        self._stop_streaming_flag = True

        if self._stock_stream:
            try:
                self._stock_stream.stop()
            except Exception as e:
                logger.debug("Error stopping stock stream: %s", e)
            self._stock_stream = None

        if self._crypto_stream:
            try:
                self._crypto_stream.stop()
            except Exception as e:
                logger.debug("Error stopping crypto stream: %s", e)
            self._crypto_stream = None

        self._is_streaming = False
        self._subscribed_symbols.clear()
        logger.info("Stopped all streams")

    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        self._init_streaming()
        return self._is_streaming

    def get_subscribed_symbols(self) -> set[str]:
        """Get set of currently subscribed symbols."""
        self._init_streaming()
        return self._subscribed_symbols.copy()

    def replay_historical(
        self,
        symbols: list[str | SymbolConfig],
        callback: Callable[[MarketDataPoint], None],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        speed: float = 1.0,
    ) -> None:
        """
        Replay historical data as simulated real-time stream.

        Useful for dry-run mode without Alpaca credentials.

        Args:
            symbols: List of symbols (strings or SymbolConfig) to replay
            callback: Function called with each MarketDataPoint
            timeframe: Bar timeframe
            start: Start datetime
            end: End datetime
            speed: Replay speed multiplier (1.0 = real-time, 0 = instant)
        """
        self._init_streaming()
        self._is_streaming = True
        self._stop_streaming_flag = False

        # Collect all bars and sort by timestamp
        all_bars: list[tuple[datetime, Bar]] = []
        for sym in symbols:
            if isinstance(sym, SymbolConfig):
                symbol = sym.symbol
                asset_class = sym.asset_type
            else:
                symbol = sym
                asset_class = None  # Will be inferred
            bars = self.fetch_bars(symbol, timeframe, start, end, asset_class)
            for bar in bars:
                all_bars.append((bar.timestamp, bar))

        all_bars.sort(key=lambda x: x[0])

        if not all_bars:
            logger.warning("No historical data found for replay")
            self._is_streaming = False
            return

        logger.info("Replaying %d bars for %d symbols", len(all_bars), len(symbols))

        # Replay bars
        prev_timestamp: Optional[datetime] = None
        for timestamp, bar in all_bars:
            if self._stop_streaming_flag:
                break

            # Simulate time delay between bars
            if speed > 0 and prev_timestamp:
                delay = (timestamp - prev_timestamp).total_seconds() / speed
                if delay > 0:
                    time.sleep(min(delay, 1.0))  # Cap delay at 1 second

            tick = MarketDataPoint(
                timestamp=bar.timestamp,
                symbol=bar.symbol,
                price=bar.close,
                volume=float(bar.volume),
            )
            callback(tick)
            prev_timestamp = timestamp

        self._is_streaming = False
        logger.info("Historical replay completed")
