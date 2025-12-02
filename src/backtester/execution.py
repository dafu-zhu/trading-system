"""
Simulate execution by feed in historical data through the gateway,
generate signals and use matching engine to simulate order status
"""
import logging
from models import Gateway, Strategy, MatchingEngine, MarketDataPoint
from typing import List, Dict, Optional
from orders.order import Order, OrderSide
from orders.order_manager import OrderManager
from orders.order_book import OrderBook
from portfolio import Portfolio, Position
from backtester.position_sizer import PositionSizer

logger = logging.getLogger("src.backtester")


class ExecutionEngine:
    def __init__(
            self,
            init_capital: float,
            gateway: Gateway,
            strategy: Strategy,
            manager: OrderManager,
            book: OrderBook,
            matching: MatchingEngine,
            position_sizer: Optional[PositionSizer] = None
    ):
        self.gateway = gateway
        self.strategy = strategy
        self.manager = manager
        self.book = book
        self.matching = matching
        self.reports = []
        self.portfolio = Portfolio(init_capital)
        # Default to 10% equity sizing if no sizer provided
        self.position_sizer = position_sizer or PositionSizer(
            sizing_method='percent_equity',
            equity_percent=0.10
        )

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
            price = signal["price"]
            side = OrderSide[signal["action"]]

            # Skip HOLD signals
            if side == OrderSide.HOLD:
                continue

            # Calculate position size using position sizer
            qty = self.position_sizer.calculate_qty(signal, self.portfolio, price)
            if qty <= 0:
                logger.warning(f"Position sizer returned qty={qty}, skipping trade")
                continue

            # Process signal into order
            order = Order(
                symbol=symbol,
                qty=qty,
                price=price,
                side=side,
                timestamp=signal["timestamp"]
            )

            # Validate order through order manager
            is_valid = self.manager.validate_order(order, self.portfolio)
            if not is_valid:
                logger.warning(f"Order {order.order_id} blocked by OrderManager")
                continue

            # Match order against order book
            report: dict = self.matching.match(order, self.book)
            self.reports.append(report)

            # TODO: Check report status to see if order was filled/rejected/partial
            # For now, assume order is filled

            # Update portfolio: add new position or update existing
            try:
                position = Position(symbol, qty, price)
                self.portfolio.add_position(position, self.portfolio.root)
                logger.info(f"Added new position: {symbol} qty={qty} @ ${price:.2f}")
            except ValueError:
                # Position already exists, update quantity
                self.portfolio.update_quantity(symbol, qty * side.value)
                self.portfolio.update_price(symbol, price)
                logger.info(f"Updated position: {symbol} qty_delta={qty * side.value} @ ${price:.2f}")

            # Update cash position
            # BUY: cash decreases (side.value = 1, so -qty * price)
            # SELL: cash increases (side.value = -1, so -qty * price * -1 = +qty * price)
            cash_delta = -qty * price * side.value
            self.portfolio.update_quantity("cash", cash_delta)
            logger.info(f"Cash updated: ${cash_delta:+.2f} (total: ${self.portfolio.get_position('cash')[0]['quantity']:.2f})")