"""
Order Gateway - CSV audit logging for all order lifecycle events.

Provides a complete audit trail of order submissions, fills, rejections,
and cancellations for regulatory compliance and debugging.
"""

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OrderEventType(Enum):
    """Order lifecycle event types."""

    SENT = "SENT"
    MODIFIED = "MODIFIED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class OrderEvent:
    """Single order lifecycle event."""

    timestamp: datetime
    event_type: OrderEventType
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float
    status: str
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    message: str = ""

    def to_csv_row(self) -> list:
        """Convert to CSV row."""
        return [
            self.timestamp.isoformat(),
            self.event_type.value,
            self.order_id,
            self.symbol,
            self.side,
            self.order_type,
            self.quantity,
            self.price,
            self.status,
            self.filled_qty,
            self.avg_fill_price,
            self.message,
        ]

    @classmethod
    def from_csv_row(cls, row: list) -> "OrderEvent":
        """Create OrderEvent from CSV row."""
        return cls(
            timestamp=datetime.fromisoformat(row[0]),
            event_type=OrderEventType(row[1]),
            order_id=row[2],
            symbol=row[3],
            side=row[4],
            order_type=row[5],
            quantity=float(row[6]),
            price=float(row[7]),
            status=row[8],
            filled_qty=float(row[9]),
            avg_fill_price=float(row[10]),
            message=row[11] if len(row) > 11 else "",
        )


CSV_HEADERS = [
    "timestamp",
    "event_type",
    "order_id",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "price",
    "status",
    "filled_qty",
    "avg_fill_price",
    "message",
]


class OrderGateway:
    """
    CSV audit logging for order lifecycle events.

    Logs all order events (sent, filled, rejected, cancelled) to a CSV file
    for regulatory compliance, debugging, and performance analysis.

    Example:
        gateway = OrderGateway("logs/orders.csv")
        gateway.log_order_sent(
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
        )
        gateway.log_order_filled(
            order_id="123",
            symbol="AAPL",
            filled_qty=100,
            avg_price=150.25,
        )
        summary = gateway.get_fill_summary()
    """

    def __init__(
        self,
        log_file: str = "logs/orders.csv",
        append: bool = True,
        dry_run_prefix: bool = False,
    ):
        """
        Initialize OrderGateway.

        Args:
            log_file: Path to CSV log file
            append: If True, append to existing file; if False, overwrite
            dry_run_prefix: If True, prefix events with DRY_RUN_
        """
        self.log_file = Path(log_file)
        self.append = append
        self.dry_run_prefix = dry_run_prefix
        self._events: list[OrderEvent] = []

        # Create directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file with headers if needed
        self._initialize_file()

        logger.info("OrderGateway initialized: %s (append=%s)", self.log_file, append)

    def _initialize_file(self) -> None:
        """Initialize CSV file with headers if needed."""
        write_headers = False

        if not self.log_file.exists():
            write_headers = True
        elif not self.append:
            write_headers = True

        if write_headers:
            mode = "w"
            with open(self.log_file, mode, newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
        else:
            # Load existing events for in-memory tracking
            self._load_existing_events()

    def _load_existing_events(self) -> None:
        """Load existing events from CSV file."""
        if not self.log_file.exists():
            return

        try:
            with open(self.log_file, newline="") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if row:
                        try:
                            event = OrderEvent.from_csv_row(row)
                            self._events.append(event)
                        except (ValueError, IndexError) as e:
                            logger.warning("Skipping invalid row: %s", e)
        except Exception as e:
            logger.error("Failed to load existing events: %s", e)

    def _write_event(self, event: OrderEvent) -> None:
        """Write event to CSV and in-memory store."""
        self._events.append(event)

        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(event.to_csv_row())

    def log_order_sent(
        self,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float,
        message: str = "",
    ) -> None:
        """
        Log order submission event.

        Args:
            order_id: Unique order identifier
            symbol: Trading symbol
            side: Order side (buy/sell)
            order_type: Order type (market/limit/stop/stop_limit)
            quantity: Order quantity
            price: Order price (limit price or expected price)
            message: Optional message
        """
        event_type = OrderEventType.SENT
        if self.dry_run_prefix:
            message = f"DRY_RUN: {message}" if message else "DRY_RUN"

        event = OrderEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="new",
            message=message,
        )
        self._write_event(event)
        logger.debug(
            "Logged %s: %s %s %s @ %.2f",
            event_type.value,
            side,
            quantity,
            symbol,
            price,
        )

    def log_order_filled(
        self,
        order_id: str,
        symbol: str,
        filled_qty: float,
        avg_price: float,
        partial: bool = False,
        message: str = "",
    ) -> None:
        """
        Log order fill event.

        Args:
            order_id: Order identifier
            symbol: Trading symbol
            filled_qty: Quantity filled
            avg_price: Average fill price
            partial: If True, this is a partial fill
            message: Optional message
        """
        event_type = OrderEventType.PARTIAL_FILL if partial else OrderEventType.FILLED

        # Get original order info
        original = self._get_last_event_for_order(order_id)
        side = original.side if original else "unknown"
        order_type = original.order_type if original else "unknown"
        quantity = original.quantity if original else filled_qty
        price = original.price if original else avg_price

        event = OrderEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="filled" if not partial else "partially_filled",
            filled_qty=filled_qty,
            avg_fill_price=avg_price,
            message=message,
        )
        self._write_event(event)
        logger.debug(
            "Logged %s: %s %s @ %.2f (filled: %.2f)",
            event_type.value,
            symbol,
            order_id,
            avg_price,
            filled_qty,
        )

    def log_order_rejected(
        self,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float,
        reason: str,
    ) -> None:
        """
        Log order rejection event.

        Args:
            order_id: Order identifier
            symbol: Trading symbol
            side: Order side
            order_type: Order type
            quantity: Order quantity
            price: Order price
            reason: Rejection reason
        """
        event = OrderEvent(
            timestamp=datetime.now(),
            event_type=OrderEventType.REJECTED,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="rejected",
            message=reason,
        )
        self._write_event(event)
        logger.debug("Logged REJECTED: %s - %s", order_id, reason)

    def log_order_cancelled(
        self,
        order_id: str,
        symbol: str,
        reason: str = "",
    ) -> None:
        """
        Log order cancellation event.

        Args:
            order_id: Order identifier
            symbol: Trading symbol
            reason: Cancellation reason
        """
        # Get original order info
        original = self._get_last_event_for_order(order_id)
        side = original.side if original else "unknown"
        order_type = original.order_type if original else "unknown"
        quantity = original.quantity if original else 0
        price = original.price if original else 0

        event = OrderEvent(
            timestamp=datetime.now(),
            event_type=OrderEventType.CANCELLED,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="cancelled",
            message=reason,
        )
        self._write_event(event)
        logger.debug("Logged CANCELLED: %s - %s", order_id, reason)

    def log_order_modified(
        self,
        order_id: str,
        symbol: str,
        new_quantity: Optional[float] = None,
        new_price: Optional[float] = None,
        message: str = "",
    ) -> None:
        """
        Log order modification event.

        Args:
            order_id: Order identifier
            symbol: Trading symbol
            new_quantity: New quantity (if modified)
            new_price: New price (if modified)
            message: Optional message
        """
        original = self._get_last_event_for_order(order_id)
        side = original.side if original else "unknown"
        order_type = original.order_type if original else "unknown"
        quantity = (
            new_quantity if new_quantity else (original.quantity if original else 0)
        )
        price = new_price if new_price else (original.price if original else 0)

        event = OrderEvent(
            timestamp=datetime.now(),
            event_type=OrderEventType.MODIFIED,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="modified",
            message=message,
        )
        self._write_event(event)
        logger.debug(
            "Logged MODIFIED: %s - qty=%.2f, price=%.2f", order_id, quantity, price
        )

    def _get_last_event_for_order(self, order_id: str) -> Optional[OrderEvent]:
        """Get the most recent event for an order."""
        for event in reversed(self._events):
            if event.order_id == order_id:
                return event
        return None

    def get_order_history(self, order_id: str) -> list[OrderEvent]:
        """
        Get all events for a specific order.

        Args:
            order_id: Order identifier

        Returns:
            List of OrderEvent objects for the order
        """
        return [e for e in self._events if e.order_id == order_id]

    def get_fill_summary(self) -> dict:
        """
        Get aggregate fill statistics.

        Returns:
            Dictionary with fill statistics:
            - total_orders: Total orders sent
            - filled_orders: Orders that were filled
            - rejected_orders: Orders that were rejected
            - cancelled_orders: Orders that were cancelled
            - partial_fills: Orders with partial fills
            - total_filled_qty: Total quantity filled
            - total_notional: Total notional value filled
            - avg_fill_price: Weighted average fill price
            - by_symbol: Per-symbol statistics
        """
        stats = {
            "total_orders": 0,
            "filled_orders": 0,
            "rejected_orders": 0,
            "cancelled_orders": 0,
            "partial_fills": 0,
            "total_filled_qty": 0.0,
            "total_notional": 0.0,
            "by_symbol": {},
        }

        seen_orders = set()

        for event in self._events:
            # Count unique orders
            if (
                event.event_type == OrderEventType.SENT
                and event.order_id not in seen_orders
            ):
                stats["total_orders"] += 1
                seen_orders.add(event.order_id)

            # Count outcomes
            if event.event_type == OrderEventType.FILLED:
                stats["filled_orders"] += 1
                stats["total_filled_qty"] += event.filled_qty
                notional = event.filled_qty * event.avg_fill_price
                stats["total_notional"] += notional

                # Per-symbol stats
                if event.symbol not in stats["by_symbol"]:
                    stats["by_symbol"][event.symbol] = {
                        "filled_qty": 0.0,
                        "notional": 0.0,
                        "count": 0,
                    }
                stats["by_symbol"][event.symbol]["filled_qty"] += event.filled_qty
                stats["by_symbol"][event.symbol]["notional"] += notional
                stats["by_symbol"][event.symbol]["count"] += 1

            elif event.event_type == OrderEventType.PARTIAL_FILL:
                stats["partial_fills"] += 1
                stats["total_filled_qty"] += event.filled_qty
                stats["total_notional"] += event.filled_qty * event.avg_fill_price

            elif event.event_type == OrderEventType.REJECTED:
                stats["rejected_orders"] += 1

            elif event.event_type == OrderEventType.CANCELLED:
                stats["cancelled_orders"] += 1

        # Calculate weighted average fill price
        if stats["total_filled_qty"] > 0:
            stats["avg_fill_price"] = (
                stats["total_notional"] / stats["total_filled_qty"]
            )
        else:
            stats["avg_fill_price"] = 0.0

        return stats

    def get_recent_events(self, n: int = 10) -> list[OrderEvent]:
        """Get the N most recent events."""
        return self._events[-n:]

    def clear(self) -> None:
        """Clear all events and reinitialize file."""
        self._events = []
        self._initialize_file()

    def __repr__(self) -> str:
        return f"OrderGateway(file={self.log_file}, events={len(self._events)})"
