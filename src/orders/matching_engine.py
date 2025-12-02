"""
MatchingEngine: Matches strategy orders against market order book.
Handles market and limit orders with realistic execution.
"""
import random
import logging
from typing import Dict, Optional
from models import MatchingEngine
from orders.order import Order, OrderState
from orders.order_book import OrderBook

logger = logging.getLogger("src.order")


class RandomMatchingEngine(MatchingEngine):
    """Simulates order matching with random outcomes."""

    def __init__(self, fill_prob: float = 0.7, partial_fill_prob: float = 0.2):
        """
        Initialize the matching engine.

        :param fill_prob: prob of fully fill (0.0 - 1.0)
        :param partial_fill_prob: prob of partial fill (0.0 - 1.0)
        """
        self.fill_prob = fill_prob
        self.partial_fill_prob = partial_fill_prob

    def match(self, order: Order, order_book: OrderBook) -> Dict:
        """
        Randomly determines if order is filled, partially filled, or canceled.
        """
        if order.state != OrderState.ACKED:
            logger.warning(f"Cannot match order {order.order_id} in state {order.state}")
            return {
                'order_id': order.order_id,
                'status': 'rejected',
                'filled_qty': 0.0,
                'remaining_qty': order.remaining_qty,
                'message': f'Order not in ACKED state: {order.state}'
            }

        # Randomly determine outcome
        outcome = random.random()

        if outcome < self.fill_prob:
            # Fully fill
            filled_qty = order.fill(order.remaining_qty)
            logger.info(f"Order {order.order_id} fully filled: {filled_qty} @ ${order.price:.2f}")
            return {
                'order_id': order.order_id,
                'status': 'filled',
                'filled_qty': filled_qty,
                'remaining_qty': 0.0,
                'fill_price': order.price,
                'message': 'Order fully filled'
            }

        elif outcome < self.fill_prob + self.partial_fill_prob:
            # Partial fill (fill 30-70% of remaining quantity)
            fill_ratio = random.uniform(0.3, 0.7)
            qty_to_fill = order.remaining_qty * fill_ratio
            filled_qty = order.fill(qty_to_fill)
            logger.info(f"Order {order.order_id} partially filled: "
                        f"{filled_qty:.2f}/{order.qty:.2f} @ ${order.price:.2f}")
            return {
                'order_id': order.order_id,
                'status': 'partially_filled',
                'filled_qty': filled_qty,
                'remaining_qty': order.remaining_qty,
                'fill_price': order.price,
                'message': f'Order partially filled: {filled_qty:.2f}/{order.qty}'
            }

        else:
            # Cancel order
            order.transition(OrderState.CANCELED)
            logger.info(f"Order {order.order_id} canceled (no match)")
            return {
                'order_id': order.order_id,
                'status': 'canceled',
                'filled_qty': 0.0,
                'remaining_qty': order.remaining_qty,
                'message': 'Order canceled (no match found)'
            }