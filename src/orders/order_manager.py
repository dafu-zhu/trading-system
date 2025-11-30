"""
OrderManager acts as a gatekeeper to validate each order
before putting it into the OrderBook
"""

from portfolio import Portfolio
from orders.order import Order, OrderSide, OrderState
from orders.risk_engine import RiskEngine

class OrderManager:
    def __init__(
            self,
            portfolio: Portfolio,
            max_order_size: float=1000,
            max_position: float=2000
    ):
        self.portfolio = portfolio
        self.max_order_size = max_order_size
        self.max_position = max_position

    def capital_sufficiency(self, order: Order) -> bool:
        """
        Check if enough capital exists to execute the order
        :return: Sufficient or not
        """
        symbol_pos = self.portfolio.get_position(order.symbol)[0]
        symbol_qty = symbol_pos["quantity"]
        cash_pos = self.portfolio.get_position("cash")[0]
        cash_val = cash_pos["quantity"] * cash_pos["price"]

        if order.side == OrderSide.BUY:
            return cash_val >= order.remaining_qty * order.price
        elif order.side == OrderSide.SELL:
            return symbol_qty >= order.remaining_qty
        else:
            raise ValueError(f"Invalid order side: {order.side}")

    def risk_limit(self, order: Order) -> bool:
        """
        Check whether
        1. order exceeds single order size
        2. position exceeds the cap after execution
        :return: Safe or not
        """
        risk_engine = RiskEngine(
            self.portfolio,
            self.max_order_size,
            self.max_position
        )
        res = risk_engine.check(order)
        return res

    def validate(self, order: Order) -> bool:
        """
        Integrate all checks and talk to order book
        :return:
        """
        is_sufficient = self.capital_sufficiency(order)
        is_safe = self.risk_limit(order)
        if is_sufficient and is_safe:
            return True
        
        return False