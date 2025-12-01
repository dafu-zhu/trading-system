import heapq
import logging
from typing import List, Tuple, Optional
from orders.order import Order, OrderState, OrderSide

logger = logging.getLogger("src.order")


class OrderBook:
    def __init__(self):
        self.ask_orders = []    # sell order, the lowest price first (min heap)
        self.bid_orders = []    # buy order, highest price first (max heap)

    def add_order(self, order: Order) -> bool:
        """Add an order to the order book without matching."""
        if order.is_sell:
            heapq.heappush(self.ask_orders, order)
        elif order.is_buy:
            heapq.heappush(self.bid_orders, order)
        else:
            return False
        return True

    def get_best_bid(self) -> Optional[Order]:
        """Get the best bid (highest buy price) without removing it."""
        return self.bid_orders[0] if self.bid_orders else None

    def get_best_ask(self) -> Optional[Order]:
        """Get the best ask (lowest sell price) without removing it."""
        return self.ask_orders[0] if self.ask_orders else None

    def get_spread(self) -> Optional[float]:
        """Get the bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None

    def get_depth(self, levels: int = 5) -> dict:
        """
        Get order book depth. Help estimate slippage.

        :param levels: Number of price levels to return
        :return: Dictionary with bids and asks
        """
        def aggregate_levels(orders: List[Order], levels: int) -> List[Tuple[float, float]]:
            """Aggregate orders by price level."""
            price_levels = {}
            for order in orders:
                if order.price not in price_levels:
                    price_levels[order.price] = 0.0
                price_levels[order.price] += order.remaining_qty

            # Sort and limit to requested levels
            sorted_levels = sorted(price_levels.items())
            return sorted_levels[:levels]

        # Get top N levels for bids (highest first)
        bid_levels = aggregate_levels(sorted(self.bid_orders, reverse=True), levels)
        bid_levels.reverse()  # Reverse to show highest first

        # Get top N levels for asks (lowest first)
        ask_levels = aggregate_levels(sorted(self.ask_orders), levels)

        return {
            'bids': bid_levels,  # [(price, quantity), ...]
            'asks': ask_levels   # [(price, quantity), ...]
        }

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order by order ID.

        :param order_id: The order ID to cancel
        :return: True if order was found and canceled
        """
        def cancel(orders: List[Order]):
            completed = False
            for i, order in enumerate(orders):
                if order.is_active and order.order_id == order_id:
                    order.transition(OrderState.CANCELED)
                    orders.pop(i)
                    heapq.heapify(orders)
                    logger.info(f"Canceled order {order_id}")
                    completed = True
            return completed

        res = False
        bid_n_ask = [self.bid_orders, self.ask_orders]
        for side_order in bid_n_ask:
            res = cancel(side_order)
            if res:
                break

        if not res:
            logger.warning(f"Order {order_id} not found in order book")

        return res

    def clear(self):
        """Clear all orders from the order book."""
        self.ask_orders.clear()
        self.bid_orders.clear()
        logger.info("Order book cleared")

    def __repr__(self) -> str:
        """String representation of the order book."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        spread = self.get_spread()

        return (f"OrderBook(bids={len(self.bid_orders)}, asks={len(self.ask_orders)}, "
                f"best_bid=${best_bid.price:.2f if best_bid else 0:.2f}, "
                f"best_ask=${best_ask.price:.2f if best_ask else 0:.2f}, "
                f"spread=${spread:.2f if spread else 0:.2f})")