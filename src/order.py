import logging
from enum import Enum, auto
from logger.logger import setup_logging

class OrderState(Enum):
    NEW = auto()
    ACKED = auto()      # Acknowledged
    FILLED = auto()
    CANCELED = auto()
    REJECTED = auto()


class Order:
    def __init__(self, symbol, qty, price, side):
        self.state = OrderState.NEW
        self.symbol = symbol
        self.qty = qty
        self.price = price
        self.side = side    # 1 BUY, 0 HOLD, -1 SELL

    def transition(self, new_state):
        allowed = {
            OrderState.NEW: {OrderState.ACKED, OrderState.REJECTED},
            OrderState.ACKED: {OrderState.FILLED, OrderState.CANCELED},
        }

        # validate the transition is legal
        legal_state = allowed.get(self.state)
        if not new_state in legal_state:
            logger = logging.getLogger("order")
            setup_logging()
            err_msg = f"Order state transition illegal, {self.state} -> {new_state}"
            logger.error(err_msg)
            raise ValueError(err_msg)

        # update order state
        self.state = new_state