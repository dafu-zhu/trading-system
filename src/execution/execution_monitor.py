"""
Execution quality tracking.

Monitors VWAP comparison and slippage metrics.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class FillRecord:
    """Record of a single fill."""

    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    order_id: Optional[str] = None
    expected_price: Optional[float] = None


@dataclass
class CompletionStatus:
    """Current completion status of execution."""

    total_planned: int = 0
    completed: int = 0
    pending: int = 0
    failed: int = 0

    @property
    def completion_pct(self) -> float:
        """Percentage of trades completed."""
        if self.total_planned == 0:
            return 100.0
        return (self.completed / self.total_planned) * 100


class ExecutionMonitor:
    """
    Tracks execution quality metrics.

    Monitors fills, calculates VWAP comparison and slippage,
    and reports completion status.

    Example:
        monitor = ExecutionMonitor()
        monitor.track_fill(order, fill_price, timestamp)
        vwap_bps = monitor.get_vwap_comparison("AAPL")
        slippage = monitor.get_slippage_report()
        status = monitor.get_completion_status()
    """

    def __init__(self):
        """Initialize execution monitor."""
        self._fills: list[FillRecord] = []
        self._fills_by_symbol: dict[str, list[FillRecord]] = {}
        self._planned_trades: dict[str, dict] = {}  # symbol -> trade info
        self._market_vwaps: dict[str, float] = {}  # symbol -> market VWAP

    def set_planned_trades(self, trades: list[dict]) -> None:
        """
        Set the planned trades for tracking.

        Args:
            trades: List of trade dicts with 'symbol', 'quantity', 'side'
        """
        self._planned_trades.clear()
        for trade in trades:
            symbol = trade.get("symbol")
            if symbol:
                self._planned_trades[symbol] = {
                    "quantity": trade.get("quantity", 0),
                    "side": trade.get("side"),
                    "filled_quantity": 0,
                    "status": "pending",
                }

    def set_market_vwap(self, symbol: str, vwap: float) -> None:
        """
        Set market VWAP for a symbol.

        Args:
            symbol: Trading symbol
            vwap: Market VWAP price
        """
        self._market_vwaps[symbol] = vwap

    def track_fill(
        self,
        symbol: str,
        side: str,
        quantity: float,
        fill_price: float,
        fill_time: datetime,
        order_id: Optional[str] = None,
        expected_price: Optional[float] = None,
    ) -> None:
        """
        Record fill for execution quality tracking.

        Args:
            symbol: Trading symbol
            side: Order side ("buy" or "sell")
            quantity: Filled quantity
            fill_price: Fill price
            fill_time: Fill timestamp
            order_id: Optional order ID
            expected_price: Expected/target price for slippage calculation
        """
        fill = FillRecord(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=fill_price,
            timestamp=fill_time,
            order_id=order_id,
            expected_price=expected_price,
        )

        self._fills.append(fill)

        if symbol not in self._fills_by_symbol:
            self._fills_by_symbol[symbol] = []
        self._fills_by_symbol[symbol].append(fill)

        # Update planned trade status
        if symbol in self._planned_trades:
            self._planned_trades[symbol]["filled_quantity"] += quantity
            planned_qty = self._planned_trades[symbol]["quantity"]
            filled_qty = self._planned_trades[symbol]["filled_quantity"]

            if filled_qty >= planned_qty:
                self._planned_trades[symbol]["status"] = "completed"
            else:
                self._planned_trades[symbol]["status"] = "partial"

        logger.debug(f"Tracked fill: {side} {quantity} {symbol} @ {fill_price}")

    def get_execution_vwap(self, symbol: str) -> Optional[float]:
        """
        Calculate execution VWAP for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Execution VWAP or None if no fills
        """
        fills = self._fills_by_symbol.get(symbol, [])
        if not fills:
            return None

        total_value = sum(f.quantity * f.price for f in fills)
        total_qty = sum(f.quantity for f in fills)

        if total_qty == 0:
            return None

        return total_value / total_qty

    def get_vwap_comparison(self, symbol: str) -> float:
        """
        Return execution price vs market VWAP in basis points.

        Positive = executed worse than VWAP (paid more for buys, received less for sells)
        Negative = executed better than VWAP

        Args:
            symbol: Trading symbol

        Returns:
            Difference in basis points
        """
        exec_vwap = self.get_execution_vwap(symbol)
        market_vwap = self._market_vwaps.get(symbol)

        if exec_vwap is None or market_vwap is None or market_vwap == 0:
            return 0.0

        # Calculate difference in basis points
        diff_pct = (exec_vwap - market_vwap) / market_vwap
        diff_bps = diff_pct * 10000

        # Adjust sign based on side
        fills = self._fills_by_symbol.get(symbol, [])
        if fills and fills[0].side.lower() == "sell":
            # For sells, worse execution is lower price
            diff_bps = -diff_bps

        return diff_bps

    def get_slippage(self, symbol: str) -> float:
        """
        Calculate slippage for a symbol in basis points.

        Uses expected_price from fills if available.

        Args:
            symbol: Trading symbol

        Returns:
            Slippage in basis points
        """
        fills = self._fills_by_symbol.get(symbol, [])
        if not fills:
            return 0.0

        # Filter fills with expected prices
        fills_with_expected = [f for f in fills if f.expected_price is not None]
        if not fills_with_expected:
            return 0.0

        total_slippage_weighted = 0.0
        total_qty = 0.0

        for fill in fills_with_expected:
            if fill.expected_price and fill.expected_price != 0:
                slippage_pct = (fill.price - fill.expected_price) / fill.expected_price
                slippage_bps = slippage_pct * 10000

                # Adjust for side
                if fill.side.lower() == "sell":
                    slippage_bps = -slippage_bps

                total_slippage_weighted += slippage_bps * fill.quantity
                total_qty += fill.quantity

        if total_qty == 0:
            return 0.0

        return total_slippage_weighted / total_qty

    def get_slippage_report(self) -> dict[str, float]:
        """
        Return slippage per symbol in basis points.

        Returns:
            Dictionary mapping symbol -> slippage bps
        """
        report = {}
        for symbol in self._fills_by_symbol:
            report[symbol] = self.get_slippage(symbol)
        return report

    def get_completion_status(self) -> CompletionStatus:
        """
        Return current completion status.

        Returns:
            CompletionStatus with counts
        """
        total = len(self._planned_trades)
        completed = sum(
            1 for t in self._planned_trades.values() if t["status"] == "completed"
        )
        failed = sum(
            1 for t in self._planned_trades.values() if t["status"] == "failed"
        )
        pending = total - completed - failed

        return CompletionStatus(
            total_planned=total,
            completed=completed,
            pending=pending,
            failed=failed,
        )

    def get_summary(self) -> dict:
        """
        Get summary of execution quality.

        Returns:
            Dictionary with execution metrics
        """
        status = self.get_completion_status()
        slippage_report = self.get_slippage_report()

        avg_slippage = 0.0
        if slippage_report:
            avg_slippage = sum(slippage_report.values()) / len(slippage_report)

        return {
            "total_fills": len(self._fills),
            "symbols_traded": len(self._fills_by_symbol),
            "completion_pct": status.completion_pct,
            "completed_trades": status.completed,
            "pending_trades": status.pending,
            "failed_trades": status.failed,
            "avg_slippage_bps": avg_slippage,
            "slippage_by_symbol": slippage_report,
        }

    def reset(self) -> None:
        """Reset all tracking data."""
        self._fills.clear()
        self._fills_by_symbol.clear()
        self._planned_trades.clear()
        self._market_vwaps.clear()
