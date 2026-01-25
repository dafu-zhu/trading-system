"""
Rate-limited priority queue for order submission.

Enforces API rate limits (e.g., 200 orders/minute for Alpaca).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
import heapq
import time
import logging

from models import OrderSide, OrderType

logger = logging.getLogger(__name__)


@dataclass
class QueuedOrder:
    """An order in the queue with priority."""

    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    priority: int = 0  # Higher = process first
    enqueue_time: datetime = field(default_factory=datetime.now)

    def __lt__(self, other: "QueuedOrder") -> bool:
        """Compare for priority queue (higher priority first)."""
        return self.priority > other.priority


@dataclass
class OrderResult:
    """Result of an order submission."""

    order: QueuedOrder
    success: bool
    fill_price: Optional[float] = None
    filled_quantity: float = 0.0
    error: Optional[str] = None
    order_id: Optional[str] = None
    submit_time: Optional[datetime] = None


class RateLimitedOrderQueue:
    """
    Priority queue with rate limiting.

    Enforces a maximum number of orders per minute to comply with
    API rate limits (e.g., Alpaca's 200 orders/minute limit).

    Example:
        queue = RateLimitedOrderQueue(max_per_minute=200)
        queue.enqueue(order, priority=10)
        results = queue.process_batch()
    """

    def __init__(
        self,
        max_per_minute: int = 200,
        submit_callback: Optional[Callable[[QueuedOrder], OrderResult]] = None,
    ):
        """
        Initialize rate-limited queue.

        Args:
            max_per_minute: Maximum orders to process per minute
            submit_callback: Optional callback for order submission
        """
        self.max_per_minute = max_per_minute
        self.submit_callback = submit_callback

        self._queue: list[QueuedOrder] = []  # Priority heap
        self._recent_submissions: list[datetime] = []  # Timestamps of recent orders
        self._results: list[OrderResult] = []

    def enqueue(self, order: QueuedOrder) -> None:
        """
        Add order to queue with priority.

        Args:
            order: Order to queue
        """
        heapq.heappush(self._queue, order)
        logger.debug(f"Enqueued {order.side.value} {order.quantity} {order.symbol} (priority={order.priority})")

    def enqueue_new(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        priority: int = 0,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> None:
        """
        Create and enqueue a new order.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            priority: Priority (higher = first)
            order_type: Order type
            limit_price: Limit price (for limit orders)
        """
        order = QueuedOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            priority=priority,
        )
        self.enqueue(order)

    def process_batch(self, batch_size: Optional[int] = None) -> list[OrderResult]:
        """
        Process orders respecting rate limit.

        Args:
            batch_size: Max orders to process (default: up to rate limit)

        Returns:
            List of OrderResult objects
        """
        # Clean up old timestamps
        self._clean_old_timestamps()

        # Calculate how many we can send
        available = self.max_per_minute - len(self._recent_submissions)
        if batch_size is not None:
            available = min(available, batch_size)

        if available <= 0:
            logger.debug("Rate limit reached, waiting...")
            return []

        results = []
        processed = 0

        while self._queue and processed < available:
            order = heapq.heappop(self._queue)
            result = self._submit_order(order)
            results.append(result)
            self._results.append(result)
            processed += 1

        if processed > 0:
            logger.info(f"Processed {processed} orders ({self.get_pending_count()} remaining)")

        return results

    def _submit_order(self, order: QueuedOrder) -> OrderResult:
        """Submit a single order."""
        now = datetime.now()
        self._recent_submissions.append(now)

        if self.submit_callback:
            try:
                result = self.submit_callback(order)
                result.submit_time = now
                return result
            except Exception as e:
                logger.error(f"Order submission failed: {e}")
                return OrderResult(
                    order=order,
                    success=False,
                    error=str(e),
                    submit_time=now,
                )
        else:
            # Dry run - simulate success
            return OrderResult(
                order=order,
                success=True,
                fill_price=order.limit_price,
                filled_quantity=order.quantity,
                submit_time=now,
            )

    def _clean_old_timestamps(self) -> None:
        """Remove timestamps older than 1 minute."""
        cutoff = datetime.now() - timedelta(minutes=1)
        self._recent_submissions = [
            ts for ts in self._recent_submissions if ts > cutoff
        ]

    def get_pending_count(self) -> int:
        """Return number of pending orders in queue."""
        return len(self._queue)

    def get_rate_usage(self) -> float:
        """Return current rate usage as percentage."""
        self._clean_old_timestamps()
        return len(self._recent_submissions) / self.max_per_minute * 100

    def get_available_capacity(self) -> int:
        """Return number of orders that can be submitted now."""
        self._clean_old_timestamps()
        return max(0, self.max_per_minute - len(self._recent_submissions))

    def wait_for_capacity(self, min_capacity: int = 1, timeout: float = 60.0) -> bool:
        """
        Wait until there's capacity to submit orders.

        Args:
            min_capacity: Minimum capacity to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if capacity available, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.get_available_capacity() >= min_capacity:
                return True
            time.sleep(0.5)

        return False

    def clear(self) -> None:
        """Clear all pending orders."""
        self._queue.clear()
        logger.info("Queue cleared")

    def get_all_results(self) -> list[OrderResult]:
        """Get all results from processed orders."""
        return self._results.copy()
