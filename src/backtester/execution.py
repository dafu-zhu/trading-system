"""
Simulate execution by feed in historical data through the gateway,
generate signals and use matching engine to simulate order status
"""
import logging
from models import Gateway, Strategy, MatchingEngine, MarketDataPoint
from typing import List, Dict
from orders.order import Order, OrderSide
from orders.order_manager import OrderManager
from orders.order_book import OrderBook
from portfolio import Portfolio, Position

logger = logging.getLogger("src.backtester")


class ExecutionEngine:
    def __init__(
            self,
            init_capital: float,
            gateway: Gateway,
            strategy: Strategy,
            manager: OrderManager,
            book: OrderBook,
            matching: MatchingEngine
    ):
        self.gateway = gateway
        self.strategy = strategy
        self.manager = manager
        self.book = book
        self.matching = matching
        self.reports = []
        self.portfolio = Portfolio(init_capital)

    def run(self):
        # Connect to data gateway
        is_connect = self.gateway.connect()
        if not is_connect:
            raise ConnectionError("Connection to Gateway failed")

        # market data point iterator
        data_points = self.gateway.stream_data()

        for tick in data_points:
            # generate signal
            signal: Dict = self.strategy.generate_signals(tick)[0]
            symbol = signal["symbol"]
            qty = 100
            price = signal["price"]
            side = OrderSide[signal["action"]]

            # Process signal into order
            order = Order(
                symbol=symbol,
                qty=qty,
                price=price,
                side=side,
                timestamp=signal["timestamp"]
            )

            # Feed order into order manager
            is_valid = self.manager.validate_order(order)
            if not is_valid:
                logger.warning(f"Order {order.order_id} blocked by OrderManager")
                continue

            # put into portfolio
            position = Position(symbol, qty, price)
            self.portfolio.add_position(position, self.portfolio.root)

            # match against order book
            report: dict = self.matching.match(order, self.book)
            self.reports.append(report)

            # update position quantity and average price
            self.portfolio.update_quantity(symbol, qty * side.value)
            self.portfolio.update_price(symbol, price)