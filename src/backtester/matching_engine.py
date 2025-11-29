import heapq
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from order import Order, OrderState, OrderSide
from logger.logger import setup_logging

logger = logging.getLogger("matching_engine")
setup_logging()


@dataclass
class Trade:
    """Represents a matched trade between two orders."""
    trade_id: int
    symbol: str
    price: float
    quantity: float
    buy_order_id: int
    sell_order_id: int
    timestamp: datetime

    def __repr__(self) -> str:
        return (f"Trade(id={self.trade_id}, {self.symbol}, "
                f"qty={self.quantity} @ ${self.price:.2f}, "
                f"buy={self.buy_order_id}, sell={self.sell_order_id})")


class OrderBook:
    """
    Order book implementation using heaps for efficient price-time priority matching.

    Uses:
        - Min heap for ask orders (sell): lowest price first
        - Max heap for bid orders (buy): highest price first (negated prices)
        - Price-time priority: best price first, then earliest timestamp

    Features:
        - Add, modify, and cancel orders
        - Automatic order matching
        - Partial fill support
        - Trade history tracking
    """

    def __init__(self, symbol: str):
        """
        Initialize order book for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'AAPL')
        """
        self.symbol = symbol

        # Heaps for order matching
        # Bids: max heap (negate prices for Python's min heap)
        # Asks: min heap
        self.bids: List[Tuple[float, int, Order]] = []  # (-price, timestamp_ns, order)
        self.asks: List[Tuple[float, int, Order]] = []  # (price, timestamp_ns, order)

        # Order lookup by ID
        self.orders: Dict[int, Order] = {}

        # Trade history
        self.trades: List[Trade] = []
        self._next_trade_id = 1

        logger.info(f"OrderBook initialized for {symbol}")

    def add_order(self, order: Order) -> List[Trade]:
        """
        Add order to the book and attempt to match.

        Args:
            order: Order to add

        Returns:
            List of trades generated from matching

        Raises:
            ValueError: If order symbol doesn't match book symbol
        """
        if order.symbol != self.symbol:
            raise ValueError(f"Order symbol {order.symbol} doesn't match book {self.symbol}")

        if order.state != OrderState.NEW:
            raise ValueError(f"Can only add NEW orders, got {order.state}")

        # Acknowledge order
        order.transition(OrderState.ACKED)
        self.orders[order.order_id] = order

        logger.info(f"Adding order to book: {order}")

        # Try to match order
        trades = self._match_order(order)

        # If order not fully filled, add to book
        if order.is_active():
            self._add_to_book(order)

        return trades

    def _add_to_book(self, order: Order) -> None:
        """Add order to appropriate heap."""
        # Convert timestamp to nanoseconds for tie-breaking
        timestamp_ns = int(order.timestamp.timestamp() * 1e9)

        if order.is_buy():
            # Max heap: negate price for Python's min heap
            heapq.heappush(self.bids, (-order.price, timestamp_ns, order))
            logger.debug(f"Added BUY order to book: {order.order_id} @ ${order.price}")
        else:
            # Min heap: use price as-is
            heapq.heappush(self.asks, (order.price, timestamp_ns, order))
            logger.debug(f"Added SELL order to book: {order.order_id} @ ${order.price}")

    def _match_order(self, order: Order) -> List[Trade]:
        """
        Match incoming order against existing orders in the book.

        Args:
            order: Order to match

        Returns:
            List of trades executed
        """
        trades = []

        if order.is_buy():
            # Match buy order against asks
            trades = self._match_buy_order(order)
        else:
            # Match sell order against bids
            trades = self._match_sell_order(order)

        return trades

    def _match_buy_order(self, buy_order: Order) -> List[Trade]:
        """Match a buy order against existing sell orders."""
        trades = []

        while buy_order.is_active() and self.asks:
            # Peek at best ask
            ask_price, _, sell_order = self.asks[0]

            # Check if match is possible (buy price >= sell price)
            if buy_order.price < ask_price:
                break

            # Remove from heap
            heapq.heappop(self.asks)

            # Skip if sell order is no longer active
            if not sell_order.is_active():
                continue

            # Execute trade
            trade = self._execute_trade(buy_order, sell_order, ask_price)
            trades.append(trade)

            # If sell order still has remaining quantity, put it back
            if sell_order.is_active():
                timestamp_ns = int(sell_order.timestamp.timestamp() * 1e9)
                heapq.heappush(self.asks, (sell_order.price, timestamp_ns, sell_order))

        return trades

    def _match_sell_order(self, sell_order: Order) -> List[Trade]:
        """Match a sell order against existing buy orders."""
        trades = []

        while sell_order.is_active() and self.bids:
            # Peek at best bid
            neg_bid_price, _, buy_order = self.bids[0]
            bid_price = -neg_bid_price

            # Check if match is possible (sell price <= buy price)
            if sell_order.price > bid_price:
                break

            # Remove from heap
            heapq.heappop(self.bids)

            # Skip if buy order is no longer active
            if not buy_order.is_active():
                continue

            # Execute trade
            trade = self._execute_trade(buy_order, sell_order, bid_price)
            trades.append(trade)

            # If buy order still has remaining quantity, put it back
            if buy_order.is_active():
                timestamp_ns = int(buy_order.timestamp.timestamp() * 1e9)
                heapq.heappush(self.bids, (-buy_order.price, timestamp_ns, buy_order))

        return trades

    def _execute_trade(self, buy_order: Order, sell_order: Order, price: float) -> Trade:
        """
        Execute a trade between buy and sell orders.

        Args:
            buy_order: Buy order
            sell_order: Sell order
            price: Trade execution price

        Returns:
            Trade object
        """
        # Determine trade quantity (minimum of remaining quantities)
        qty = min(buy_order.remaining_qty, sell_order.remaining_qty)

        # Fill both orders
        buy_order.fill(qty)
        sell_order.fill(qty)

        # Create trade
        trade = Trade(
            trade_id=self._next_trade_id,
            symbol=self.symbol,
            price=price,
            quantity=qty,
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            timestamp=datetime.now()
        )
        self._next_trade_id += 1

        self.trades.append(trade)
        logger.info(f"Trade executed: {trade}")

        return trade

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id: ID of order to cancel

        Returns:
            True if cancelled, False if order not found or not active
        """
        order = self.orders.get(order_id)

        if order is None:
            logger.warning(f"Order {order_id} not found")
            return False

        if not order.is_active():
            logger.warning(f"Order {order_id} not active (state: {order.state})")
            return False

        # Transition to cancelled state
        order.transition(OrderState.CANCELED)
        logger.info(f"Order {order_id} cancelled")

        # Note: We don't remove from heap immediately (lazy deletion)
        # It will be skipped during matching
        return True

    def modify_order(self, order_id: int, new_qty: Optional[float] = None,
                    new_price: Optional[float] = None) -> bool:
        """
        Modify an existing order.

        Note: This cancels the old order and creates a new one.

        Args:
            order_id: ID of order to modify
            new_qty: New quantity (optional)
            new_price: New price (optional)

        Returns:
            True if modified successfully
        """
        order = self.orders.get(order_id)

        if order is None or not order.is_active():
            return False

        # Cancel existing order
        self.cancel_order(order_id)

        # Create new order with modifications
        new_order = Order(
            symbol=order.symbol,
            qty=new_qty if new_qty is not None else order.remaining_qty,
            price=new_price if new_price is not None else order.price,
            side=order.side,
            timestamp=datetime.now()
        )

        # Add new order
        self.add_order(new_order)
        logger.info(f"Order {order_id} modified -> new order {new_order.order_id}")

        return True

    def get_order(self, order_id: int) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_best_bid(self) -> Optional[float]:
        """Get best (highest) bid price."""
        while self.bids:
            neg_price, _, order = self.bids[0]
            if order.is_active():
                return -neg_price
            heapq.heappop(self.bids)  # Remove inactive order
        return None

    def get_best_ask(self) -> Optional[float]:
        """Get best (lowest) ask price."""
        while self.asks:
            price, _, order = self.asks[0]
            if order.is_active():
                return price
            heapq.heappop(self.asks)  # Remove inactive order
        return None

    def get_spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid is not None and ask is not None:
            return ask - bid
        return None

    def get_mid_price(self) -> Optional[float]:
        """Get mid price (average of best bid and ask)."""
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid is not None and ask is not None:
            return (bid + ask) / 2
        return None

    def get_depth(self, levels: int = 5) -> Dict[str, List[Tuple[float, float]]]:
        """
        Get market depth (top N levels).

        Args:
            levels: Number of price levels to return

        Returns:
            Dict with 'bids' and 'asks', each containing (price, total_qty) tuples
        """
        # Aggregate quantities by price level
        bid_levels = defaultdict(float)
        ask_levels = defaultdict(float)

        # Process bids
        for neg_price, _, order in self.bids:
            if order.is_active():
                price = -neg_price
                bid_levels[price] += order.remaining_qty

        # Process asks
        for price, _, order in self.asks:
            if order.is_active():
                ask_levels[price] += order.remaining_qty

        # Get top N levels
        top_bids = sorted(bid_levels.items(), reverse=True)[:levels]
        top_asks = sorted(ask_levels.items())[:levels]

        return {
            'bids': top_bids,
            'asks': top_asks
        }

    def get_trade_history(self, limit: Optional[int] = None) -> List[Trade]:
        """
        Get trade history.

        Args:
            limit: Max number of trades to return (most recent)

        Returns:
            List of trades
        """
        if limit is None:
            return self.trades.copy()
        return self.trades[-limit:]

    def clear(self) -> None:
        """Clear all orders and trades."""
        self.bids.clear()
        self.asks.clear()
        self.orders.clear()
        self.trades.clear()
        logger.info(f"OrderBook cleared for {self.symbol}")

    def __repr__(self) -> str:
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        spread = self.get_spread()

        return (f"OrderBook({self.symbol}, "
                f"bid=${bid:.2f if bid else 0}, "
                f"ask=${ask:.2f if ask else 0}, "
                f"spread=${spread:.2f if spread else 0}, "
                f"orders={len([o for o in self.orders.values() if o.is_active()])}, "
                f"trades={len(self.trades)})")


if __name__ == '__main__':
    print("=" * 70)
    print("OrderBook Example")
    print("=" * 70)

    # Create order book
    book = OrderBook('AAPL')
    print(f"\nInitialized: {book}")

    # Add some buy orders
    print("\n" + "=" * 70)
    print("Adding BUY orders...")
    print("=" * 70)
    buy1 = Order('AAPL', qty=100, price=150.00, side=OrderSide.BUY)
    buy2 = Order('AAPL', qty=50, price=150.50, side=OrderSide.BUY)
    buy3 = Order('AAPL', qty=75, price=149.50, side=OrderSide.BUY)

    book.add_order(buy1)
    book.add_order(buy2)
    book.add_order(buy3)

    print(f"\n{book}")
    print(f"Best bid: ${book.get_best_bid()}")
    print(f"Best ask: ${book.get_best_ask()}")

    # Add some sell orders
    print("\n" + "=" * 70)
    print("Adding SELL orders...")
    print("=" * 70)
    sell1 = Order('AAPL', qty=60, price=151.00, side=OrderSide.SELL)
    sell2 = Order('AAPL', qty=40, price=150.75, side=OrderSide.SELL)

    book.add_order(sell1)
    book.add_order(sell2)

    print(f"\n{book}")
    print(f"Best bid: ${book.get_best_bid()}")
    print(f"Best ask: ${book.get_best_ask()}")
    print(f"Spread: ${book.get_spread()}")

    # Add sell order that matches
    print("\n" + "=" * 70)
    print("Adding SELL order that matches (price=150.25)...")
    print("=" * 70)
    sell_match = Order('AAPL', qty=120, price=150.25, side=OrderSide.SELL)
    trades = book.add_order(sell_match)

    print(f"\nTrades executed: {len(trades)}")
    for trade in trades:
        print(f"  {trade}")

    print(f"\n{book}")

    # Show market depth
    print("\n" + "=" * 70)
    print("Market Depth (Top 5 levels)")
    print("=" * 70)
    depth = book.get_depth(5)
    print("\nBids:")
    for price, qty in depth['bids']:
        print(f"  ${price:.2f} | {qty:.0f}")
    print("\nAsks:")
    for price, qty in depth['asks']:
        print(f"  ${price:.2f} | {qty:.0f}")

    # Cancel an order
    print("\n" + "=" * 70)
    print(f"Cancelling order {buy1.order_id}...")
    print("=" * 70)
    book.cancel_order(buy1.order_id)
    print(f"\n{book}")

    # Show trade history
    print("\n" + "=" * 70)
    print("Trade History")
    print("=" * 70)
    for trade in book.get_trade_history():
        print(f"  {trade}")
