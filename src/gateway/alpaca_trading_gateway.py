"""
Alpaca Trading Gateway implementation.

Provides order submission, cancellation, and account/position queries
via the Alpaca API.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, cast

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopOrderRequest,
    StopLimitOrderRequest,
)
from alpaca.trading.enums import (
    OrderSide as AlpacaOrderSide,
    TimeInForce as AlpacaTimeInForce,
    OrderStatus as AlpacaOrderStatus,
    OrderType as AlpacaOrderType,
)
from alpaca.common.exceptions import APIError

from models import (
    TradingGateway,
    OrderSide,
    OrderType,
    TimeInForce,
    AccountInfo,
    PositionInfo,
    OrderResult,
)

logger = logging.getLogger(__name__)
# Import at runtime for cast() to work
from alpaca.trading.models import TradeAccount, Position


class AlpacaTradingGateway(TradingGateway):
    """
    Trading gateway implementation for Alpaca API.

    Supports paper and live trading accounts. Warns if using live keys.
    """

    # Alpaca paper trading URL
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize Alpaca trading gateway.

        :param api_key: Alpaca API key (defaults to ALPACA_API_KEY env var)
        :param api_secret: Alpaca API secret (defaults to ALPACA_API_SECRET env var)
        :param base_url: API base URL (defaults to ALPACA_BASE_URL env var or paper)
        """
        self._api_key = api_key or os.getenv("ALPACA_API_KEY")
        self._api_secret = api_secret or os.getenv("ALPACA_API_SECRET")
        self._base_url = base_url or os.getenv("ALPACA_BASE_URL", self.PAPER_URL)

        if not self._api_key or not self._api_secret:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and "
                "ALPACA_API_SECRET environment variables or pass them directly."
            )

        self._client: Optional[TradingClient] = None
        self._connected = False
        self._is_paper = self._base_url == self.PAPER_URL

        # Warn if using live keys
        if not self._is_paper:
            logger.warning(
                "WARNING: Using LIVE Alpaca API. Real money at risk! "
                "Set ALPACA_BASE_URL to %s for paper trading.",
                self.PAPER_URL,
            )

    def connect(self) -> bool:
        """Connect to Alpaca trading API."""
        try:
            self._client = TradingClient(
                api_key=self._api_key,
                secret_key=self._api_secret,
                paper=self._is_paper,
            )
            # Verify connection by fetching account
            account = cast(TradeAccount, self._client.get_account())
            self._connected = True
            logger.info(
                "Connected to Alpaca %s trading. Account: %s",
                "paper" if self._is_paper else "LIVE",
                account.account_number,
            )
            return True
        except APIError as e:
            logger.error("Failed to connect to Alpaca: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Alpaca trading API."""
        self._client = None
        self._connected = False
        logger.info("Disconnected from Alpaca trading API")

    def is_connected(self) -> bool:
        """Check if connected to Alpaca."""
        return self._connected and self._client is not None

    def _ensure_connected(self) -> None:
        """Raise error if not connected."""
        if not self.is_connected():
            raise RuntimeError("Not connected to Alpaca. Call connect() first.")

    @property 
    def _valid_client(self) -> TradingClient:
        if self._client is None:
            raise RuntimeError("Not connected")
        return self._client

    def _map_order_side(self, side: OrderSide) -> AlpacaOrderSide:
        """Map internal OrderSide to Alpaca OrderSide."""
        return AlpacaOrderSide.BUY if side == OrderSide.BUY else AlpacaOrderSide.SELL

    def _map_time_in_force(self, tif: TimeInForce) -> AlpacaTimeInForce:
        """Map internal TimeInForce to Alpaca TimeInForce."""
        mapping = {
            TimeInForce.DAY: AlpacaTimeInForce.DAY,
            TimeInForce.GTC: AlpacaTimeInForce.GTC,
            TimeInForce.IOC: AlpacaTimeInForce.IOC,
            TimeInForce.FOK: AlpacaTimeInForce.FOK,
        }
        return mapping[tif]

    def _map_order_status(self, status: AlpacaOrderStatus) -> str:
        """Map Alpaca OrderStatus to string."""
        mapping = {
            AlpacaOrderStatus.NEW: "new",
            AlpacaOrderStatus.ACCEPTED: "new",
            AlpacaOrderStatus.PENDING_NEW: "new",
            AlpacaOrderStatus.PARTIALLY_FILLED: "partially_filled",
            AlpacaOrderStatus.FILLED: "filled",
            AlpacaOrderStatus.CANCELED: "canceled",
            AlpacaOrderStatus.REJECTED: "rejected",
            AlpacaOrderStatus.EXPIRED: "canceled",
            AlpacaOrderStatus.REPLACED: "new",
        }
        return mapping.get(status, "unknown")

    def _alpaca_order_to_result(self, order) -> OrderResult:
        """Convert Alpaca order object to OrderResult."""
        return OrderResult(
            order_id=str(order.id),
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=OrderSide.BUY if order.side == AlpacaOrderSide.BUY else OrderSide.SELL,
            order_type=self._map_alpaca_order_type(order.order_type),
            quantity=float(order.qty),
            filled_quantity=float(order.filled_qty) if order.filled_qty else 0.0,
            status=self._map_order_status(order.status),
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
        )

    def _map_alpaca_order_type(self, order_type: AlpacaOrderType) -> OrderType:
        """Map Alpaca order type to internal OrderType."""
        mapping = {
            AlpacaOrderType.MARKET: OrderType.MARKET,
            AlpacaOrderType.LIMIT: OrderType.LIMIT,
            AlpacaOrderType.STOP: OrderType.STOP,
            AlpacaOrderType.STOP_LIMIT: OrderType.STOP_LIMIT,
        }
        return mapping.get(order_type, OrderType.MARKET)

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """Submit an order to Alpaca."""
        self._ensure_connected()

        alpaca_side = self._map_order_side(side)

        # Crypto orders require GTC (Good Till Cancelled), not DAY
        is_crypto = "/" in symbol
        if is_crypto and time_in_force == TimeInForce.DAY:
            alpaca_tif = AlpacaTimeInForce.GTC
        else:
            alpaca_tif = self._map_time_in_force(time_in_force)

        try:
            if order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    client_order_id=client_order_id,
                )
            elif order_type == OrderType.LIMIT:
                if limit_price is None:
                    raise ValueError("limit_price required for LIMIT orders")
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    limit_price=limit_price,
                    client_order_id=client_order_id,
                )
            elif order_type == OrderType.STOP:
                if stop_price is None:
                    raise ValueError("stop_price required for STOP orders")
                request = StopOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    stop_price=stop_price,
                    client_order_id=client_order_id,
                )
            elif order_type == OrderType.STOP_LIMIT:
                if limit_price is None or stop_price is None:
                    raise ValueError("limit_price and stop_price required for STOP_LIMIT orders")
                request = StopLimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    client_order_id=client_order_id,
                )
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            order = self._valid_client.submit_order(request)
            result = self._alpaca_order_to_result(order)
            logger.info(
                "Order submitted: %s %s %s @ %s, ID: %s",
                side.value,
                quantity,
                symbol,
                order_type.value,
                result.order_id,
            )
            return result

        except APIError as e:
            logger.error("Order submission failed: %s", e)
            return OrderResult(
                order_id="",
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                filled_quantity=0.0,
                status="rejected",
                message=str(e),
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID."""
        self._ensure_connected()

        try:
            self._valid_client.cancel_order_by_id(order_id)
            logger.info("Order canceled: %s", order_id)
            return True
        except APIError as e:
            logger.error("Failed to cancel order %s: %s", order_id, e)
            return False

    def get_order(self, order_id: str) -> Optional[OrderResult]:
        """Get order status by ID."""
        self._ensure_connected()

        try:
            order = self._valid_client.get_order_by_id(order_id)
            return self._alpaca_order_to_result(order)
        except APIError as e:
            logger.error("Failed to get order %s: %s", order_id, e)
            return None

    def get_account(self) -> AccountInfo:
        """Get current account information."""
        self._ensure_connected()

        account = cast(TradeAccount, self._valid_client.get_account())
        return AccountInfo(
            account_id=account.account_number,
            cash=float(account.cash or "0"),
            portfolio_value=float(account.portfolio_value or "0"),
            buying_power=float(account.buying_power or "0"),
            equity=float(account.equity or "0"),
            currency=str(account.currency),
            is_paper=self._is_paper,
        )

    def get_positions(self) -> list[PositionInfo]:
        """Get all current positions."""
        self._ensure_connected()

        positions = cast(list[Position], self._valid_client.get_all_positions())
        return [
            PositionInfo(
                symbol=pos.symbol,
                quantity=float(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                market_value=float(pos.market_value or "0"),
                unrealized_pl=float(pos.unrealized_pl or "0"),
                side="long" if float(pos.qty) > 0 else "short",
            )
            for pos in positions
        ]

    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """Get position for a specific symbol."""
        self._ensure_connected()

        try:
            pos = cast(Position, self._valid_client.get_open_position(symbol))
            return PositionInfo(
                symbol=pos.symbol,
                quantity=float(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                market_value=float(pos.market_value or "0"),
                unrealized_pl=float(pos.unrealized_pl or "0"),
                side="long" if float(pos.qty) > 0 else "short",
            )
        except APIError:
            return None
