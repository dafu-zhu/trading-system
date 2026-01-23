"""
Coinbase Data Gateway implementation.

Provides real-time crypto market data via Coinbase WebSocket API.
No API key required for public market data.
"""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Callable

import websockets

from models import DataGateway, Bar, Timeframe, MarketCalendarDay, MarketDataPoint
from config.trading_config import DataType, SymbolConfig

logger = logging.getLogger(__name__)


class CoinbaseDataGateway(DataGateway):
    """
    Data gateway for Coinbase WebSocket API.

    Provides free real-time crypto market data without authentication.
    Supports matches (trades) and ticker data.
    """

    WS_URL = "wss://ws-feed.exchange.coinbase.com"

    def __init__(self):
        """Initialize Coinbase data gateway."""
        self._connected = False
        self._websocket = None
        self._stream_callback: Optional[Callable[[MarketDataPoint], None]] = None
        self._subscribed_symbols: set[str] = set()
        self._is_streaming = False
        self._stop_streaming_flag = False
        self._stream_thread: Optional[threading.Thread] = None
        self._first_data_received = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def connect(self) -> bool:
        """Connect to Coinbase (no auth required for public data)."""
        self._connected = True
        logger.info("Coinbase data gateway ready (no auth required)")
        return True

    def disconnect(self) -> None:
        """Disconnect from Coinbase."""
        self.stop_streaming()
        self._connected = False
        logger.info("Disconnected from Coinbase data gateway")

    def is_connected(self) -> bool:
        """Check if gateway is connected."""
        return self._connected

    def _convert_symbol(self, symbol: str) -> str:
        """
        Convert standard symbol format to Coinbase format.

        Examples:
            BTC/USD -> BTC-USD
            ETH/USDT -> ETH-USD (Coinbase uses USD, not USDT)
        """
        # Replace slash with dash
        symbol = symbol.replace("/", "-")
        # Convert USDT to USD (Coinbase uses USD)
        symbol = symbol.replace("-USDT", "-USD")
        return symbol.upper()

    def _convert_symbol_back(self, coinbase_symbol: str) -> str:
        """
        Convert Coinbase symbol format back to standard format.

        Examples:
            BTC-USD -> BTC/USD
        """
        return coinbase_symbol.replace("-", "/")

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "match" or msg_type == "last_match":
                await self._handle_match(data)
            elif msg_type == "ticker":
                await self._handle_ticker(data)
            elif msg_type == "error":
                logger.error("Coinbase error: %s", data.get("message"))
            elif msg_type == "subscriptions":
                logger.info("Coinbase subscriptions confirmed: %s", data.get("channels"))

        except json.JSONDecodeError as e:
            logger.error("Failed to parse message: %s", e)
        except Exception as e:
            logger.exception("Error handling message: %s", e)

    async def _handle_match(self, data: dict) -> None:
        """Handle match (trade) message."""
        if self._stream_callback is None:
            return

        if not self._first_data_received:
            self._first_data_received = True
            logger.info("First trade received - Coinbase stream is active")

        symbol = self._convert_symbol_back(data.get("product_id", ""))
        price = float(data.get("price", 0))
        size = float(data.get("size", 0))
        time_str = data.get("time", "")

        try:
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(timezone.utc)

        tick = MarketDataPoint(
            timestamp=timestamp.replace(tzinfo=None),
            symbol=symbol,
            price=price,
            volume=size,
        )

        logger.debug("Coinbase trade: %s @ %.2f", symbol, tick.price)
        self._stream_callback(tick)

    async def _handle_ticker(self, data: dict) -> None:
        """Handle ticker message."""
        if self._stream_callback is None:
            return

        if not self._first_data_received:
            self._first_data_received = True
            logger.info("First ticker received - Coinbase stream is active")

        symbol = self._convert_symbol_back(data.get("product_id", ""))
        price = float(data.get("price", 0))
        volume = float(data.get("last_size", 0))
        time_str = data.get("time", "")

        try:
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(timezone.utc)

        tick = MarketDataPoint(
            timestamp=timestamp.replace(tzinfo=None),
            symbol=symbol,
            price=price,
            volume=volume,
            bid_price=float(data.get("best_bid", 0)) if data.get("best_bid") else None,
            ask_price=float(data.get("best_ask", 0)) if data.get("best_ask") else None,
        )

        self._stream_callback(tick)

    async def _run_websocket(self, symbols: list[str], channel: str) -> None:
        """Run WebSocket connection with automatic reconnection."""
        product_ids = [self._convert_symbol(s) for s in symbols]
        reconnect_delay = 1  # Start with 1 second
        max_reconnect_delay = 60  # Max 60 seconds between retries

        while not self._stop_streaming_flag:
            logger.info("Connecting to Coinbase WebSocket...")

            try:
                async with websockets.connect(self.WS_URL) as ws:
                    self._websocket = ws
                    logger.info("Connected to Coinbase WebSocket")
                    reconnect_delay = 1  # Reset delay on successful connect

                    # Subscribe to channel
                    subscribe_msg = json.dumps({
                        "type": "subscribe",
                        "product_ids": product_ids,
                        "channels": [channel]
                    })
                    await ws.send(subscribe_msg)
                    logger.info("Subscribed to %s for %s", channel, product_ids)

                    # Read messages
                    while not self._stop_streaming_flag:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=30)
                            await self._handle_message(message)
                        except asyncio.TimeoutError:
                            # Send heartbeat / keep alive
                            pass
                        except websockets.ConnectionClosed as e:
                            logger.warning("Coinbase WebSocket closed: %s. Reconnecting...", e)
                            break

            except Exception as e:
                logger.error("Coinbase WebSocket error: %s", e)

            finally:
                self._websocket = None

            # Reconnect with exponential backoff (unless stopped)
            if not self._stop_streaming_flag:
                logger.info("Reconnecting in %d seconds...", reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

        logger.info("Coinbase WebSocket stream stopped")

    def _run_stream_sync(self, symbols: list[str], channel: str) -> None:
        """Run WebSocket stream synchronously (for threading)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_websocket(symbols, channel))
        finally:
            self._loop.close()
            self._loop = None

    def stream_realtime(
        self,
        symbols: list[str] | list[SymbolConfig],
        callback: Callable[[MarketDataPoint], None],
        data_type: DataType = DataType.TRADES,
        **kwargs,
    ) -> None:
        """
        Stream real-time market data (blocking).

        Args:
            symbols: List of symbols or SymbolConfig objects
            callback: Function called with each MarketDataPoint
            data_type: Type of data to stream (TRADES or QUOTES)
        """
        # Extract symbol strings from SymbolConfig objects if needed
        symbol_strings = []
        for sym in symbols:
            if isinstance(sym, SymbolConfig):
                symbol_strings.append(sym.symbol)
            else:
                symbol_strings.append(sym)

        self._stream_callback = callback
        self._subscribed_symbols = set(symbol_strings)
        self._is_streaming = True
        self._stop_streaming_flag = False
        self._first_data_received = False

        # Map data type to Coinbase channel
        if data_type == DataType.TRADES:
            channel = "matches"
        elif data_type == DataType.QUOTES:
            channel = "ticker"
        else:
            channel = "matches"

        logger.info("Subscribing to Coinbase %s for: %s", channel, symbol_strings)
        self._run_stream_sync(symbol_strings, channel)

    def start_streaming(
        self,
        symbols: list[str],
        callback: Callable[[MarketDataPoint], None],
        data_type: DataType = DataType.TRADES,
        **kwargs,
    ) -> None:
        """
        Start streaming in a background thread (non-blocking).

        Args:
            symbols: List of symbols
            callback: Function called with each MarketDataPoint
            data_type: Type of data to stream
        """
        if self._is_streaming:
            logger.warning("Already streaming. Stop first before restarting.")
            return

        self._stream_thread = threading.Thread(
            target=self.stream_realtime,
            args=(symbols, callback, data_type),
            daemon=True,
        )
        self._stream_thread.start()
        logger.info("Started Coinbase streaming in background thread")

    def stop_streaming(self) -> None:
        """Stop streaming market data."""
        self._stop_streaming_flag = True
        self._is_streaming = False

        # Close WebSocket if running
        if self._websocket and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._websocket.close(), self._loop
            )

        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=5)

        self._subscribed_symbols.clear()
        logger.info("Stopped Coinbase streams")

    # Historical data methods - not supported
    def fetch_bars(self, symbol: str, timeframe: Timeframe, start, end) -> list[Bar]:
        """Not implemented - use Alpaca for historical data."""
        raise NotImplementedError("Coinbase gateway only supports real-time streaming")

    def stream_bars(self, symbol: str, timeframe: Timeframe, start, end):
        """Not implemented - use Alpaca for historical data."""
        raise NotImplementedError("Coinbase gateway only supports real-time streaming")

    def get_market_calendar(self, start, end) -> list[MarketCalendarDay]:
        """Crypto markets are 24/7 - no calendar needed."""
        return []

    def get_latest_bar(self, symbol: str, timeframe: Timeframe) -> Optional[Bar]:
        """Not implemented - use Alpaca for historical data."""
        return None
