import heapq
from execution.order import Order, OrderSide


class OrderBook:
    def __init__(self):
        self.ask_orders = []    # sell order, the lowest price first (min heap)
        self.bid_orders = []    # buy order, highest price first (max heap)

    def add_order(self, order: Order) -> bool:
        if order.is_sell:
            heapq.heappush(self.ask_orders, order)
        elif order.is_buy:
            heapq.heappush(self.bid_orders, order)
        else:
            return False
        return True

    def execute_order(self, order: Order):
        pass