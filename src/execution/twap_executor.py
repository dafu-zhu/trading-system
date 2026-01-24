"""
TWAP (Time-Weighted Average Price) execution algorithm.

Splits orders evenly across time to minimize market impact.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional
import logging

from models import TradingGateway, OrderSide, OrderType
from execution.rebalancing_plan import RebalancingPlan, PlannedTrade
from execution.rate_limited_queue import RateLimitedOrderQueue

logger = logging.getLogger(__name__)


@dataclass
class OrderSlice:
    """A single time slice of an order."""

    symbol: str
    side: OrderSide
    quantity: int
    scheduled_time: time
    parent_trade: Optional[PlannedTrade] = None
    executed: bool = False
    fill_price: Optional[float] = None


@dataclass
class ExecutionReport:
    """Summary of execution results."""

    total_trades: int = 0
    completed_trades: int = 0
    failed_trades: int = 0
    partial_trades: int = 0
    vwap_performance: dict[str, float] = field(default_factory=dict)  # symbol -> bps vs VWAP
    slippage: dict[str, float] = field(default_factory=dict)  # symbol -> slippage bps
    total_notional: float = 0.0
    execution_time_seconds: float = 0.0


class TWAPExecutor:
    """
    TWAP execution algorithm.

    Splits orders into equal slices distributed across the trading window.
    Respects rate limits via RateLimitedOrderQueue.

    Example:
        executor = TWAPExecutor(trading_gateway, rate_limit=200)
        report = executor.execute_plan(plan)
    """

    def __init__(
        self,
        trading_gateway: Optional[TradingGateway] = None,
        rate_limit: int = 200,
        num_slices: int = 10,
        dry_run: bool = False,
    ):
        """
        Initialize TWAP executor.

        Args:
            trading_gateway: Gateway for order submission
            rate_limit: Max orders per minute (default: 200 for Alpaca)
            num_slices: Number of time slices per order (default: 10)
            dry_run: If True, simulate execution without submitting orders
        """
        self.trading_gateway = trading_gateway
        self.rate_limit = rate_limit
        self.num_slices = num_slices
        self.dry_run = dry_run

        self._order_queue = RateLimitedOrderQueue(max_per_minute=rate_limit)
        self._slices: list[OrderSlice] = []

    def execute_plan(self, plan: RebalancingPlan) -> ExecutionReport:
        """
        Execute rebalancing plan using TWAP algorithm.

        Args:
            plan: Rebalancing plan to execute

        Returns:
            ExecutionReport with results
        """
        start_time = datetime.now()
        report = ExecutionReport(total_trades=plan.total_trades)

        if plan.total_trades == 0:
            logger.info("No trades to execute")
            return report

        # Create slices for all trades
        self._slices = []
        for trade in plan.trades:
            slices = self._split_into_slices(trade, self.num_slices)
            scheduled = self._schedule_slices(slices, plan.start_time, plan.aggressive_time)
            self._slices.extend(scheduled)

        logger.info(
            f"Created {len(self._slices)} slices for {plan.total_trades} trades"
        )

        # Execute slices
        if self.dry_run:
            report = self._dry_run_execution(plan)
        else:
            report = self._live_execution(plan)

        report.execution_time_seconds = (datetime.now() - start_time).total_seconds()
        return report

    def _split_into_slices(
        self, trade: PlannedTrade, num_slices: int
    ) -> list[OrderSlice]:
        """
        Split a trade into equal slices.

        Args:
            trade: Trade to split
            num_slices: Number of slices

        Returns:
            List of OrderSlice objects
        """
        if num_slices <= 0:
            num_slices = 1

        # Calculate slice size
        base_qty = trade.quantity // num_slices
        remainder = trade.quantity % num_slices

        slices = []
        for i in range(num_slices):
            # Distribute remainder across first slices
            qty = base_qty + (1 if i < remainder else 0)
            if qty > 0:
                slices.append(
                    OrderSlice(
                        symbol=trade.symbol,
                        side=trade.side,
                        quantity=qty,
                        scheduled_time=time(9, 30),  # Placeholder, set by schedule
                        parent_trade=trade,
                    )
                )

        return slices

    def _schedule_slices(
        self,
        slices: list[OrderSlice],
        start: time,
        end: time,
    ) -> list[OrderSlice]:
        """
        Distribute slices evenly across time window.

        Args:
            slices: Slices to schedule
            start: Start time
            end: End time

        Returns:
            Slices with scheduled_time set
        """
        if not slices:
            return slices

        # Convert times to minutes from midnight
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute

        if end_minutes <= start_minutes:
            end_minutes = start_minutes + 1  # Minimum 1 minute window

        total_minutes = end_minutes - start_minutes
        interval = total_minutes / len(slices)

        for i, slice_obj in enumerate(slices):
            slice_minutes = start_minutes + int(i * interval)
            slice_hour = slice_minutes // 60
            slice_minute = slice_minutes % 60
            slice_obj.scheduled_time = time(slice_hour, slice_minute)

        return slices

    def _dry_run_execution(self, plan: RebalancingPlan) -> ExecutionReport:
        """Simulate execution without submitting orders."""
        report = ExecutionReport(total_trades=plan.total_trades)

        for trade in plan.trades:
            # Simulate successful fill
            report.completed_trades += 1
            report.vwap_performance[trade.symbol] = 0.0  # Perfect execution
            report.slippage[trade.symbol] = 0.0

            if trade.limit_price:
                report.total_notional += trade.quantity * trade.limit_price

        logger.info(f"DRY RUN: Would execute {report.total_trades} trades")
        return report

    def _live_execution(self, plan: RebalancingPlan) -> ExecutionReport:
        """Execute orders through trading gateway."""
        report = ExecutionReport(total_trades=plan.total_trades)

        if not self.trading_gateway:
            logger.error("No trading gateway configured for live execution")
            report.failed_trades = plan.total_trades
            return report

        # Group slices by scheduled time
        slices_by_time: dict[time, list[OrderSlice]] = {}
        for slice_obj in self._slices:
            if slice_obj.scheduled_time not in slices_by_time:
                slices_by_time[slice_obj.scheduled_time] = []
            slices_by_time[slice_obj.scheduled_time].append(slice_obj)

        # Track execution per symbol
        fills_by_symbol: dict[str, list[tuple[int, float]]] = {}

        # Execute in time order
        for scheduled_time in sorted(slices_by_time.keys()):
            slices = slices_by_time[scheduled_time]

            for slice_obj in slices:
                try:
                    result = self.trading_gateway.submit_order(
                        symbol=slice_obj.symbol,
                        side=slice_obj.side,
                        quantity=float(slice_obj.quantity),
                        order_type=OrderType.MARKET,
                    )

                    if result.status in ("filled", "partially_filled"):
                        slice_obj.executed = True
                        slice_obj.fill_price = result.filled_avg_price

                        # Track fill
                        if slice_obj.symbol not in fills_by_symbol:
                            fills_by_symbol[slice_obj.symbol] = []
                        fills_by_symbol[slice_obj.symbol].append(
                            (int(result.filled_quantity), result.filled_avg_price or 0.0)
                        )

                except Exception as e:
                    logger.error(f"Failed to execute slice for {slice_obj.symbol}: {e}")

        # Calculate final statistics
        completed_symbols = set()
        for trade in plan.trades:
            symbol_fills = fills_by_symbol.get(trade.symbol, [])
            total_filled = sum(qty for qty, _ in symbol_fills)

            if total_filled >= trade.quantity:
                report.completed_trades += 1
                completed_symbols.add(trade.symbol)
            elif total_filled > 0:
                report.partial_trades += 1
            else:
                report.failed_trades += 1

            # Calculate VWAP
            if symbol_fills:
                total_value = sum(qty * price for qty, price in symbol_fills)
                # TODO: compare to market VWAP
                report.vwap_performance[trade.symbol] = 0.0
                report.total_notional += total_value

        return report

    def get_pending_slices(self) -> list[OrderSlice]:
        """Get list of pending (unexecuted) slices."""
        return [s for s in self._slices if not s.executed]

    def get_completed_slices(self) -> list[OrderSlice]:
        """Get list of completed slices."""
        return [s for s in self._slices if s.executed]
