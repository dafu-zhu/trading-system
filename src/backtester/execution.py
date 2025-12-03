"""
Simulate execution by feed in historical data through the gateway,
generate signals and use matching engine to simulate order status
"""
import logging
from models import Gateway, Strategy, MatchingEngine, MarketDataPoint
from typing import List, Dict, Optional
from orders.order import Order, OrderSide, OrderState
from orders.order_manager import OrderManager
from orders.order_book import OrderBook
from portfolio import Portfolio, Position
from backtester.position_sizer import PositionSizer, PercentSizer
from backtester.trade_tracker import TradeTracker

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
        # Track current market prices for mark-to-market
        self.current_prices = {}
        # Track completed trades for analysis
        self.trade_tracker = TradeTracker()
        # Default to 10% equity sizing if no sizer provided
        self.position_sizer = position_sizer or PercentSizer(
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

            # Determine side multiplier
            side_mul = float(side.value)

            # Update current market price for this symbol
            self.current_prices[symbol] = price

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

            # Acknowledge validate order
            order.transition(OrderState.ACKED)

            # Match order against order book
            report: dict = self.matching.match(order, self.book)
            self.reports.append(report)

            # Process report - only update portfolio if order was actually filled
            status = report.get('status')
            filled_qty = report.get('filled_qty', 0.0)
            fill_price = report.get('fill_price', price)

            if status in ['filled', 'partially_filled'] and filled_qty > 0:
                # Track this fill for trade analysis
                self.trade_tracker.process_fill(
                    symbol=symbol,
                    side=side,
                    filled_qty=filled_qty,
                    fill_price=fill_price,
                    timestamp=order.timestamp,
                    order_id=order.order_id
                )

                # Use actual fill quantity and price from report
                # Update portfolio: add new position or update existing
                try:
                    position = Position(symbol, filled_qty, fill_price)
                    self.portfolio.add_position(position, self.portfolio.root)
                    logger.info(f"Added new position: {symbol} qty={filled_qty:.2f} @ ${fill_price:.2f}")
                except ValueError:
                    # Position already exists, update quantity and weighted average price
                    existing_pos = self.portfolio.get_position(symbol)[0]
                    existing_qty = existing_pos['quantity']
                    existing_price = existing_pos['price']

                    # Calculate new weighted average price
                    total_qty = existing_qty + (filled_qty * side_mul)
                    if total_qty != 0:
                        new_avg_price = (
                            (existing_qty * existing_price + filled_qty * fill_price * side_mul) / total_qty
                        )
                    else:
                        new_avg_price = fill_price

                    # Update position
                    self.portfolio.update_quantity(symbol, filled_qty * side_mul)
                    self.portfolio.update_price(symbol, abs(new_avg_price))
                    logger.info(f"Updated position: {symbol} qty_delta={filled_qty * side_mul:.2f} @ ${fill_price:.2f} (avg: ${abs(new_avg_price):.2f})")

                # Update cash position
                # BUY: cash decreases (side.value = 1, so -qty * price)
                # SELL: cash increases (side.value = -1, so -qty * price * -1 = +qty * price)
                cash_delta = -filled_qty * fill_price * side_mul
                self.portfolio.update_quantity("cash", cash_delta)
                logger.info(f"Cash updated: ${cash_delta:+.2f} (total: ${self.portfolio.get_position('cash')[0]['quantity']:.2f})")
            elif status == 'canceled':
                logger.info(f"Order {order.order_id} canceled - no portfolio update")
            elif status == 'rejected':
                logger.warning(f"Order {order.order_id} rejected - no portfolio update")
            else:
                logger.warning(f"Order {order.order_id} status '{status}' - no portfolio update")

            # Mark portfolio to market at end of backtest
            self.mark_to_market()

    def mark_to_market(self):
        """Update all positions to current market prices for accurate valuation."""
        positions = self.portfolio.get_positions()
        for pos in positions:
            symbol = pos['symbol']
            # Skip cash - it's always at price = 1
            if symbol == 'cash':
                continue
            # Update to current market price if we have it
            if symbol in self.current_prices:
                current_price = self.current_prices[symbol]
                old_price = pos['price']
                # TODO: How to update stock price
                logger.info(f"Marked {symbol} to market: ${old_price:.2f} -> ${current_price:.2f}")