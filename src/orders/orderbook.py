import heapq
import logging
from typing import List, Tuple, Optional
from orders.order import Order, OrderState

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

    def execute_order(self, order: Order) -> List[Tuple[Order, Order, float, float]]:
        """
        Execute an order by matching it against existing orders in the book.
        :param order: The incoming order to execute
        :return: List of tuples (incoming_order, matched_order, quantity, price)
        """
        executions = []

        # Acknowledge the order first
        if order.state == OrderState.NEW:
            order.transition(OrderState.ACKED)

        # Determine which side to match against
        if order.is_buy:
            # Buy order matches against sell orders (asks)
            opposite_side = self.ask_orders
        elif order.is_sell:
            # Sell order matches against buy orders (bids)
            opposite_side = self.bid_orders
        else:
            logger.warning(f"Order {order.order_id} has invalid side: {order.side}")
            return executions

        # Try to match the order
        while order.remaining_qty > 0 and opposite_side:
            # Peek at the best order on the opposite side
            best_order = opposite_side[0]

            # Check if orders can match
            if not self._can_match(order, best_order):
                break

            # Remove the best order from the heap
            heapq.heappop(opposite_side)

            # Calculate match quantity
            match_qty = min(order.remaining_qty, best_order.remaining_qty)

            # Execute the match at the best order's price (price-time priority)
            execution_price = best_order.price

            # Fill both orders
            order.fill(match_qty)
            best_order.fill(match_qty)

            # Record the execution
            executions.append((order, best_order, match_qty, execution_price))

            logger.info(f"Matched {match_qty} units @ ${execution_price:.2f}: "
                       f"Order {order.order_id} ({order.side.name}) <-> "
                       f"Order {best_order.order_id} ({best_order.side.name})")

            # If the best order still has remaining quantity, put it back
            if best_order.remaining_qty > 0:
                heapq.heappush(opposite_side, best_order)

        # If the order has remaining quantity, add it to the book
        if order.remaining_qty > 0:
            self.add_order(order)
            logger.debug(f"Order {order.order_id} added to book with {order.remaining_qty} remaining")

        return executions

    def _can_match(self, incoming_order: Order, book_order: Order) -> bool:
        """
        Check if two orders can match based on price.

        :param incoming_order: The incoming order
        :param book_order: The order from the book
        :return: True if orders can match
        """
        if incoming_order.is_buy and book_order.is_sell:
            # Buy order can match if its price >= ask price
            return incoming_order.price >= book_order.price
        elif incoming_order.is_sell and book_order.is_buy:
            # Sell order can match if its price <= bid price
            return incoming_order.price <= book_order.price
        return False

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
        # Search in bid orders
        for i, order in enumerate(self.bid_orders):
            if order.order_id == order_id:
                if order.is_active:
                    order.transition(OrderState.CANCELED)
                    self.bid_orders.pop(i)
                    heapq.heapify(self.bid_orders)
                    logger.info(f"Canceled order {order_id} from bids")
                    return True

        # Search in ask orders
        for i, order in enumerate(self.ask_orders):
            if order.order_id == order_id:
                if order.is_active:
                    order.transition(OrderState.CANCELED)
                    self.ask_orders.pop(i)
                    heapq.heapify(self.ask_orders)
                    logger.info(f"Canceled order {order_id} from asks")
                    return True

        logger.warning(f"Order {order_id} not found in order book")
        return False

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