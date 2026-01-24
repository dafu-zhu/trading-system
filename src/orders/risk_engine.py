from portfolio import Portfolio
from orders.order import Order


class RiskEngine:
    def __init__(
            self,
            portfolio: Portfolio,
            max_order_size: float=1000,
            max_position: float=2000
    ):
        self._portfolio = portfolio
        self.max_order_size = max_order_size
        self.max_position = max_position

    def check(self, order: Order) -> bool:
        res = True
        if order.qty > self.max_order_size:
            res = False

        symbol_pos = self._portfolio.get_position(order.symbol)[0]
        current_qty = symbol_pos["quantity"]
        if abs(current_qty + order.qty * order.side.value) > self.max_position:
            res = False

        return res
