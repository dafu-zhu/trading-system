"""
Aggressive completion handler for end-of-day execution.

Converts remaining limit orders to market orders at cutoff time.
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional
import logging

from models import OrderSide, OrderType
from execution.rebalancing_plan import PlannedTrade

logger = logging.getLogger(__name__)


@dataclass
class AggressiveOrder:
    """An aggressive market order converted from pending trade."""

    symbol: str
    side: OrderSide
    quantity: int
    original_limit_price: Optional[float] = None
    reason: str = "cutoff_time"


class AggressiveCompletionHandler:
    """
    Handles aggressive completion of trades at end of day.

    Converts remaining limit orders to market orders when cutoff time
    is reached (default: 3:30 PM, 30 minutes before market close).

    Example:
        handler = AggressiveCompletionHandler(cutoff_time=time(15, 30))
        aggressive_orders = handler.check_and_escalate(pending_trades)
    """

    def __init__(
        self,
        cutoff_time: time = time(15, 30),
        buffer_minutes: int = 30,
    ):
        """
        Initialize aggressive completion handler.

        Args:
            cutoff_time: Time to switch to aggressive completion (default 3:30 PM)
            buffer_minutes: Minutes before market close for aggressive mode
        """
        self.cutoff_time = cutoff_time
        self.buffer_minutes = buffer_minutes
        self._escalated_symbols: set[str] = set()

    def is_cutoff_reached(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if cutoff time has been reached.

        Args:
            current_time: Current datetime (default: now)

        Returns:
            True if cutoff reached
        """
        if current_time is None:
            current_time = datetime.now()

        current_time_only = current_time.time()
        return current_time_only >= self.cutoff_time

    def check_and_escalate(
        self,
        pending_trades: list[PlannedTrade],
        current_time: Optional[datetime] = None,
    ) -> list[AggressiveOrder]:
        """
        Convert remaining limit orders to market orders at cutoff time.

        Args:
            pending_trades: List of pending trades
            current_time: Current datetime (default: now)

        Returns:
            List of aggressive market orders to execute
        """
        if not self.is_cutoff_reached(current_time):
            return []

        aggressive_orders = []

        for trade in pending_trades:
            # Skip if already escalated
            if trade.symbol in self._escalated_symbols:
                continue

            aggressive_order = AggressiveOrder(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                original_limit_price=trade.limit_price,
                reason="cutoff_time_reached",
            )

            aggressive_orders.append(aggressive_order)
            self._escalated_symbols.add(trade.symbol)

            logger.warning(
                f"AGGRESSIVE: Converting {trade.symbol} to market order "
                f"({trade.quantity} {trade.side.value})"
            )

        if aggressive_orders:
            logger.warning(
                f"Escalated {len(aggressive_orders)} trades to aggressive completion"
            )

        return aggressive_orders

    def should_use_market_order(
        self,
        trade: PlannedTrade,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Determine if a trade should use market order.

        Args:
            trade: Trade to check
            current_time: Current datetime

        Returns:
            True if market order should be used
        """
        if current_time is None:
            current_time = datetime.now()

        # After cutoff, always use market orders
        if self.is_cutoff_reached(current_time):
            return True

        # If no limit price specified, use market
        if trade.limit_price is None:
            return True

        return False

    def get_order_type(
        self,
        trade: PlannedTrade,
        current_time: Optional[datetime] = None,
    ) -> OrderType:
        """
        Get appropriate order type for a trade.

        Args:
            trade: Trade to check
            current_time: Current datetime

        Returns:
            OrderType.MARKET or OrderType.LIMIT
        """
        if self.should_use_market_order(trade, current_time):
            return OrderType.MARKET
        return OrderType.LIMIT

    def get_escalated_symbols(self) -> set[str]:
        """Get set of symbols that have been escalated."""
        return self._escalated_symbols.copy()

    def reset(self) -> None:
        """Reset escalation tracking for new trading day."""
        self._escalated_symbols.clear()
        logger.info("Aggressive handler reset for new trading day")
