"""
Finnhub Data Gateway implementation.

Provides real-time stock market data via Finnhub WebSocket API.
Free tier: 60 API calls/minute, real-time WebSocket streaming.
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional, Callable

import websockets

from models import DataGateway, Bar, Timeframe, MarketCalendarDay, MarketDataPoint
from config.trading_config import DataType, SymbolConfig

logger = logging.getLogger(__name__)


class FinnhubDataGateway(DataGateway):
    """
    Data gateway for Finnhub WebSocket API.

    Provides free real-time stock market data.
    Requires API key (free tier available at finnhub.io).
    """

    WS_URL = "wss://ws.finnhub.io"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Finnhub data gateway.

        Args:
            api_key: Finnhub API key (defaults to FINNHUB_API_KEY env var)
        """
        self._api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Finnhub API key required. Set FINNHUB_API_KEY environment variable "
                "or pass api_key parameter. Get free key at https://finnhub.io"
            )

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
        """Connect to Finnhub."""
        self._connected = True
        logger.info("Finnhub data gateway ready")
        return True

    def disconnect(self) -> None:
        """Disconnect from Finnhub."""
        self.stop_streaming()
        self._connected = False
        logger.info("Disconnected from Finnhub data gateway")

    def is_connected(self) -> bool:
        """Check if gateway is connected."""
        return self._connected

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "trade":
                await self._handle_trades(data.get("data", []))
            elif msg_type == "ping":
                # Finnhub sends pings, no response needed
                pass
            elif msg_type == "error":
                logger.error("Finnhub error: %s", data.get("msg"))

        except json.JSONDecodeError as e:
            logger.error("Failed to parse message: %s", e)
        except Exception as e:
            logger.exception("Error handling message: %s", e)

    async def _handle_trades(self, trades: list[dict]) -> None:
        """Handle trade messages."""
        if self._stream_callback is None:
            return

        for trade in trades:
            if not self._first_data_received:
                self._first_data_received = True
                logger.info("First trade received - Finnhub stream is active")

            # Finnhub trade format: {"c":["1"],"p":150.5,"s":"AAPL","t":1234567890123,"v":100}
            symbol = trade.get("s", "")
            price = trade.get("p", 0.0)
            volume = trade.get("v", 0.0)
            timestamp_ms = trade.get("t", 0)

            timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

            tick = MarketDataPoint(
                timestamp=timestamp.replace(tzinfo=None),
                symbol=symbol,
                price=float(price),
                volume=float(volume),
            )

            logger.debug("Finnhub trade: %s @ %.2f", symbol, tick.price)
            self._stream_callback(tick)

    async def _run_websocket(self, symbols: list[str]) -> None:
        """Run WebSocket connection."""
        url = f"{self.WS_URL}?token={self._api_key}"
        logger.info("Connecting to Finnhub WebSocket...")

        try:
            async with websockets.connect(url) as ws:
                self._websocket = ws
                logger.info("Connected to Finnhub WebSocket")

                # Subscribe to symbols
                for symbol in symbols:
                    subscribe_msg = json.dumps({
                        "type": "subscribe",
                        "symbol": symbol
                    })
                    await ws.send(subscribe_msg)
                    logger.info("Subscribed to %s", symbol)

                # Read messages
                while not self._stop_streaming_flag:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=30)
                        await self._handle_message(message)
                    except asyncio.TimeoutError:
                        # No message in 30s, connection still alive
                        pass
                    except websockets.ConnectionClosed:
                        logger.warning("Finnhub WebSocket connection closed")
                        break

        except Exception as e:
            logger.error("Finnhub WebSocket error: %s", e)
        finally:
            self._websocket = None
            logger.info("Finnhub WebSocket stream stopped")

    def _run_stream_sync(self, symbols: list[str]) -> None:
        """Run WebSocket stream synchronously (for threading)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_websocket(symbols))
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
            symbols: List of stock symbols or SymbolConfig objects
            callback: Function called with each MarketDataPoint
            data_type: Type of data to stream (only TRADES supported)
        """
        # Extract symbol strings from SymbolConfig objects if needed
        symbol_strings = []
        for sym in symbols:
            if isinstance(sym, SymbolConfig):
                symbol_strings.append(sym.symbol)
            else:
                symbol_strings.append(sym)

        if data_type != DataType.TRADES:
            logger.warning("Finnhub only supports TRADES, ignoring data_type=%s", data_type)

        self._stream_callback = callback
        self._subscribed_symbols = set(symbol_strings)
        self._is_streaming = True
        self._stop_streaming_flag = False
        self._first_data_received = False

        logger.info("Subscribing to Finnhub streams: %s", symbol_strings)
        self._run_stream_sync(symbol_strings)

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
            symbols: List of stock symbols
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
        logger.info("Started Finnhub streaming in background thread")

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
        logger.info("Stopped Finnhub streams")

    # Historical data methods - not fully supported
    def fetch_bars(self, symbol: str, timeframe: Timeframe, start, end) -> list[Bar]:
        """Not implemented - use Alpaca for historical data."""
        raise NotImplementedError("Finnhub gateway only supports real-time streaming")

    def stream_bars(self, symbol: str, timeframe: Timeframe, start, end):
        """Not implemented - use Alpaca for historical data."""
        raise NotImplementedError("Finnhub gateway only supports real-time streaming")

    def get_market_calendar(self, start, end) -> list[MarketCalendarDay]:
        """Not implemented - use Alpaca for market calendar."""
        return []

    def get_latest_bar(self, symbol: str, timeframe: Timeframe) -> Optional[Bar]:
        """Not implemented."""
        return None
