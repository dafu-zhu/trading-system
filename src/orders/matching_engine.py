"""
MatchingEngine: Matches strategy orders against market data.
Handles market and limit orders with deterministic execution.
"""

import logging
from typing import Optional

from models import Bar, MatchingEngine
from orders.order import Order, OrderSide, OrderState

logger = logging.getLogger("src.order")


class DeterministicMatchingEngine(MatchingEngine):
    """
    Deterministic matching engine for backtesting.

    Fills orders based on bar data with reproducible results.
    Uses close price for market orders and checks if limit price
    was hit during the bar for limit orders.
    """

    def __init__(
        self,
        fill_at: str = "close",
        max_volume_pct: float = 0.1,
        slippage_bps: float = 0.0,
    ):
        """
        Initialize deterministic matching engine.

        :param fill_at: Price to fill at ("open", "close", "vwap")
        :param max_volume_pct: Maximum fill as percentage of bar volume (0.1 = 10%)
        :param slippage_bps: Slippage in basis points (10 = 0.1%)
        """
        self.fill_at = fill_at
        self.max_volume_pct = max_volume_pct
        self.slippage_bps = slippage_bps
        self._current_bar: Optional[Bar] = None

    def set_current_bar(self, bar: Bar) -> None:
        """Set the current bar for matching context."""
        self._current_bar = bar

    def match(self, order: Order) -> dict:
        """
        Match order against current bar data.

        For market orders: fill at specified price (close/open/vwap)
        For limit orders: check if limit price was within bar range

        :param order: Order to match
        :param order_book: Order book (not used in bar-based matching)
        :return: Execution report dictionary
        """
        if order.state != OrderState.ACKED:
            logger.warning(f"Cannot match order {order.order_id} in state {order.state}")
            return {
                'order_id': order.order_id,
                'status': 'rejected',
                'filled_qty': 0.0,
                'remaining_qty': order.remaining_qty,
                'message': f'Order not in ACKED state: {order.state}'
            }

        if self._current_bar is None:
            logger.warning(f"No bar data for matching order {order.order_id}")
            return {
                'order_id': order.order_id,
                'status': 'rejected',
                'filled_qty': 0.0,
                'remaining_qty': order.remaining_qty,
                'message': 'No bar data available for matching'
            }

        bar = self._current_bar

        # Determine fill price based on configuration
        fill_price = self._get_fill_price(bar, order)
        if fill_price is None:
            # Limit order not fillable at current bar
            return {
                'order_id': order.order_id,
                'status': 'pending',
                'filled_qty': 0.0,
                'remaining_qty': order.remaining_qty,
                'message': 'Limit price not within bar range'
            }

        # Apply slippage
        fill_price = self._apply_slippage(fill_price, order)

        # Calculate fillable quantity based on volume
        max_fill_qty = bar.volume * self.max_volume_pct
        fill_qty = min(order.remaining_qty, max_fill_qty)

        if fill_qty <= 0:
            return {
                'order_id': order.order_id,
                'status': 'rejected',
                'filled_qty': 0.0,
                'remaining_qty': order.remaining_qty,
                'message': 'Insufficient volume for fill'
            }

        # Execute fill
        filled_qty = order.fill(fill_qty)

        if order.remaining_qty <= 0:
            status = 'filled'
            message = 'Order fully filled'
        else:
            status = 'partially_filled'
            message = f'Order partially filled: {filled_qty:.2f}/{order.qty}'

        logger.info(f"Order {order.order_id} {status}: {filled_qty:.6f} @ ${fill_price:.2f}")

        return {
            'order_id': order.order_id,
            'status': status,
            'filled_qty': filled_qty,
            'remaining_qty': order.remaining_qty,
            'fill_price': fill_price,
            'message': message
        }

    def _get_fill_price(self, bar: Bar, order: Order) -> Optional[float]:
        """
        Get fill price based on order type and bar data.

        :param bar: Current bar
        :param order: Order to fill
        :return: Fill price or None if limit order not fillable
        """
        limit_price = getattr(order, 'limit_price', None)

        # For limit orders, check if price was hit during bar
        if limit_price is not None:
            if bar.low <= limit_price <= bar.high:
                return limit_price
            return None

        # For market orders, use configured fill price
        price_map = {"open": bar.open, "vwap": bar.vwap, "close": bar.close}
        price = price_map.get(self.fill_at)
        return price if price is not None else bar.close

    def _apply_slippage(self, price: float, order: Order) -> float:
        """
        Apply slippage to fill price.

        :param price: Base fill price
        :param order: Order (for direction)
        :return: Price with slippage applied
        """
        if self.slippage_bps <= 0:
            return price

        slippage_pct = self.slippage_bps / 10000.0
        # Buy orders get worse price (higher), sell orders get worse (lower)
        direction = 1 if order.side == OrderSide.BUY else -1
        return price * (1 + direction * slippage_pct)