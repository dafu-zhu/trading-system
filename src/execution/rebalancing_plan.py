"""
Rebalancing plan data structures and planner.

Converts target positions into prioritized trades for execution.
"""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from models import OrderSide


@dataclass
class PlannedTrade:
    """A single trade in a rebalancing plan."""

    symbol: str
    side: OrderSide
    quantity: int
    priority: int = 0  # Higher = execute first (based on trade size)
    limit_price: Optional[float] = None  # None = market order

    @property
    def notional_value(self) -> float:
        """Estimated notional value (requires price)."""
        if self.limit_price:
            return self.quantity * self.limit_price
        return 0.0


@dataclass
class RebalancingPlan:
    """Complete rebalancing plan for a trading day."""

    target_date: date
    trades: list[PlannedTrade] = field(default_factory=list)
    start_time: time = field(default_factory=lambda: time(9, 30))  # Market open
    aggressive_time: time = field(default_factory=lambda: time(15, 30))  # 30 min before close

    @property
    def total_trades(self) -> int:
        """Total number of trades in plan."""
        return len(self.trades)

    @property
    def total_buys(self) -> int:
        """Number of buy trades."""
        return sum(1 for t in self.trades if t.side == OrderSide.BUY)

    @property
    def total_sells(self) -> int:
        """Number of sell trades."""
        return sum(1 for t in self.trades if t.side == OrderSide.SELL)

    def get_trades_by_priority(self) -> list[PlannedTrade]:
        """Get trades sorted by priority (highest first)."""
        return sorted(self.trades, key=lambda t: t.priority, reverse=True)


class RebalancingPlanner:
    """
    Creates rebalancing plans from position differences.

    Computes trades needed to move from current positions to target positions,
    assigns priorities based on trade size (largest first).
    """

    def __init__(
        self,
        start_time: time = time(9, 30),
        aggressive_time: time = time(15, 30),
    ):
        """
        Initialize planner.

        Args:
            start_time: Time to start executing trades
            aggressive_time: Time to switch to aggressive completion
        """
        self.start_time = start_time
        self.aggressive_time = aggressive_time

    def create_plan(
        self,
        current_positions: dict[str, int],
        target_positions: dict[str, int],
        target_date: Optional[date] = None,
        current_prices: Optional[dict[str, float]] = None,
    ) -> RebalancingPlan:
        """
        Create rebalancing plan from current to target positions.

        Args:
            current_positions: Current position quantities by symbol
            target_positions: Target position quantities by symbol
            target_date: Date for execution (default: today)
            current_prices: Current prices for limit order calculation

        Returns:
            RebalancingPlan with prioritized trades
        """
        from datetime import date as date_type

        if target_date is None:
            target_date = date_type.today()

        trades = []

        # Get all symbols
        all_symbols = set(current_positions.keys()) | set(target_positions.keys())

        for symbol in all_symbols:
            current = current_positions.get(symbol, 0)
            target = target_positions.get(symbol, 0)
            diff = target - current

            if diff == 0:
                continue

            # Determine side and quantity
            if diff > 0:
                side = OrderSide.BUY
                quantity = diff
            else:
                side = OrderSide.SELL
                quantity = abs(diff)

            # Get limit price if available
            limit_price = current_prices.get(symbol) if current_prices else None

            trade = PlannedTrade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                priority=0,  # Will be set below
                limit_price=limit_price,
            )
            trades.append(trade)

        # Assign priorities based on trade size (largest first)
        self._assign_priorities(trades, current_prices)

        return RebalancingPlan(
            target_date=target_date,
            trades=trades,
            start_time=self.start_time,
            aggressive_time=self.aggressive_time,
        )

    def _assign_priorities(
        self,
        trades: list[PlannedTrade],
        prices: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Assign priorities to trades based on notional value.

        Larger trades get higher priority to ensure they complete.
        """
        if not trades:
            return

        # Calculate notional values
        notional_values = []
        for trade in trades:
            if prices and trade.symbol in prices:
                value = trade.quantity * prices[trade.symbol]
            else:
                value = trade.quantity  # Fall back to quantity

            notional_values.append((trade, value))

        # Sort by value descending
        notional_values.sort(key=lambda x: x[1], reverse=True)

        # Assign priorities (highest value = highest priority)
        for i, (trade, _) in enumerate(notional_values):
            trade.priority = len(trades) - i
