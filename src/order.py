import logging
from enum import Enum, auto
from datetime import datetime
from typing import Optional
from logger.logger import setup_logging

logger = logging.getLogger("order")
setup_logging()


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = 1
    SELL = -1
    HOLD = 0


class OrderState(Enum):
    NEW = auto()
    ACKED = auto()      # Acknowledged
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELED = auto()
    REJECTED = auto()


class Order:
    """
    Represents a trading order with support for partial fills.
    """
    _next_order_id = 1

    def __init__(
        self,
        symbol: str,
        qty: float,
        price: float,
        side: OrderSide,
        order_id: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ):
        self.order_id = order_id if order_id is not None else Order._next_order_id
        if order_id is None:
            Order._next_order_id += 1

        self.symbol = symbol
        self.qty = qty
        self.filled_qty = 0.0
        self.remaining_qty = qty
        self.price = price
        self.side = side
        self.timestamp = timestamp if timestamp else datetime.now()
        self.state = OrderState.NEW

    def transition(self, new_state: OrderState):
        """Transition order to a new state with validation."""
        allowed = {
            OrderState.NEW: {OrderState.ACKED, OrderState.REJECTED},
            OrderState.ACKED: {OrderState.FILLED, OrderState.PARTIALLY_FILLED, OrderState.CANCELED},
            OrderState.PARTIALLY_FILLED: {OrderState.FILLED, OrderState.CANCELED},
        }

        # validate the transition is legal
        legal_state = allowed.get(self.state)
        if legal_state is None or new_state not in legal_state:
            err_msg = f"Order state transition illegal: {self.state} -> {new_state}"
            logger.error(err_msg)
            raise ValueError(err_msg)

        # update order state
        self.state = new_state
        logger.debug(f"Order {self.order_id} state: {self.state}")

    def fill(self, qty: float) -> float:
        """
        Fill (partially or fully) the order.

        Args:
            qty: Quantity to fill

        Returns:
            Actual quantity filled
        """
        if qty <= 0:
            raise ValueError(f"Fill quantity must be positive, got {qty}")

        if self.state not in [OrderState.ACKED, OrderState.PARTIALLY_FILLED]:
            raise ValueError(f"Cannot fill order in state {self.state}")

        # Calculate actual fill quantity
        actual_fill = min(qty, self.remaining_qty)

        self.filled_qty += actual_fill
        self.remaining_qty -= actual_fill

        # Update state
        if self.remaining_qty <= 0:
            self.state = OrderState.FILLED
        else:
            self.state = OrderState.PARTIALLY_FILLED

        logger.info(f"Order {self.order_id} filled {actual_fill} @ ${self.price} "
                   f"(total: {self.filled_qty}/{self.qty})")

        return actual_fill

    def is_buy(self) -> bool:
        """Check if order is a buy order."""
        return self.side == OrderSide.BUY

    def is_sell(self) -> bool:
        """Check if order is a sell order."""
        return self.side == OrderSide.SELL

    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.state == OrderState.FILLED

    def is_active(self) -> bool:
        """Check if order is active (can be filled)."""
        return self.state in [OrderState.ACKED, OrderState.PARTIALLY_FILLED]

    def __repr__(self) -> str:
        return (f"Order(id={self.order_id}, {self.symbol}, "
                f"{self.side.name}, qty={self.qty}, "
                f"filled={self.filled_qty}, price=${self.price:.2f}, "
                f"state={self.state.name})")

    def __lt__(self, other):
        """Comparison for heap ordering (price-time priority)."""
        # For buy orders (max heap): higher price first, then earlier time
        # For sell orders (min heap): lower price first, then earlier time
        if self.price != other.price:
            return self.price < other.price
        return self.timestamp > other.timestamp