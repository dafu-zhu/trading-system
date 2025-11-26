from enum import Enum, auto

class OrderState(Enum):
    NEW = auto()
    ACKED = auto()      # Acknowledged
    FILLED = auto()
    CANCELED = auto()
    REJECTED = auto()

class Order:
    def __init__(self, symbol, qty, side):
        self.state = OrderState.NEW

    def transition(self, new_state):
        allowed = {
            OrderState.NEW: {OrderState.ACKED, OrderState.REJECTED},
            OrderState.ACKED: {OrderState.FILLED, OrderState.CANCELED},
        }

        # validate the transition is legal
        legal_state = allowed.get(self.state)
        if not new_state in legal_state:
            raise ValueError(f"Order state transition illegal, {self.state} -> {new_state}")

        # update order state
        self.state = new_state
