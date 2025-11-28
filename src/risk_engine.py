from trader.portfolio import Portfolio
from trader.order import Order


class RiskEngine:
    def __init__(
            self,
            portfolio: Portfolio,
            max_order_size=1000,
            max_position=2000
    ):
        self._portfolio = portfolio
        self.max_order_size = max_order_size
        self.max_position = max_position

    def check(self, order: Order) -> bool:
        res = True
        if order.qty > self.max_order_size:
            res = False

        symbol_pos = self._portfolio.get_position(order.symbol)
        if symbol_pos + order.qty * order.side > self.max_position:
            res = False

        return res
