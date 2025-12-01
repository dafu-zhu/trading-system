"""
Simulate realistic order execution outcome
"""

import random
from orders.order import OrderState, Order
from orders.order_book import OrderBook
from orders.order_manager import OrderManager

random.seed(10)

class MatchingSimulator:
    def __init__(self, book: OrderBook):
        self.book = book

    @staticmethod
    def _execution_status() -> OrderState:
        dice = random.random()
        if dice < 0.8:
            return OrderState.FILLED
        elif dice < 0.9:
            return OrderState.PARTIALLY_FILLED
        else:
            return OrderState.CANCELED

    def match_all(self) -> list:
        """
        Traverse all orders in the orderbook, pop them out, and simulate execution.

        :return: List of execution tuples (order, matched_order, match_qty, execution_price)
                 Format matches deterministic matching: (order, best_order, match_qty, execution_price)
                 For simulator, matched_order is None since there's no real counterparty.
        """
        executions = []

        # Process all bid orders (buy orders)
        while self.book.bid_orders:
            order = self.book.bid_orders.pop(0)
            execution = self._match_single(order)
            executions.extend(execution)

        # Process all ask orders (sell orders)
        while self.book.ask_orders:
            order = self.book.ask_orders.pop(0)
            execution = self._match_single(order)
            executions.extend(execution)

        return executions

    def _match_single(self, order: Order) -> list:
        """
        Simulate execution for a single order using random outcome.

        :param order: The order to execute
        :return: List of execution tuples (order, matched_order, match_qty, execution_price)
                 matched_order is None for simulated execution
        """
        executions = []

        # Acknowledge the order first
        if order.state == OrderState.NEW:
            order.transition(OrderState.ACKED)

        # Determine outcome randomly
        outcome = self._execution_status()

        if outcome == OrderState.FILLED:
            # Fill entire remaining quantity
            executed_qty = order.remaining_qty
            order.fill(executed_qty)
            executions.append((order, None, executed_qty, order.price))

        elif outcome == OrderState.PARTIALLY_FILLED:
            # Fill random portion (10% to 90%)
            fill_ratio = random.uniform(0.1, 0.9)
            executed_qty = order.remaining_qty * fill_ratio
            order.fill(executed_qty)
            executions.append((order, None, executed_qty, order.price))

        elif outcome == OrderState.CANCELED:
            # Cancel without execution
            order.transition(OrderState.CANCELED)

        return executions

