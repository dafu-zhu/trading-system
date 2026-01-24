"""
Backtest engine for running strategy simulations on historical data.

Uses DataGateway to fetch bars and DeterministicMatchingEngine for fills.
"""

import logging
from datetime import datetime
from typing import Optional

from models import DataGateway, Timeframe, Bar, MarketSnapshot, Strategy, OrderSide
from orders.order import Order, OrderState
from orders.order_manager import OrderManager
from orders.matching_engine import DeterministicMatchingEngine
from portfolio import Portfolio, Position
from backtester.position_sizer import PositionSizer, PercentSizer
from backtester.trade_tracker import TradeTracker
from backtester.equity_tracker import EquityTracker

logger = logging.getLogger("src.backtester")


class BacktestEngine:
    """
    Backtest engine using DataGateway and deterministic matching.

    Processes bars from DataGateway, generates signals via strategy,
    and executes orders through deterministic matching engine.
    """

    def __init__(
        self,
        gateway: DataGateway,
        strategy: Strategy,
        init_capital: float = 100000.0,
        position_sizer: Optional[PositionSizer] = None,
        slippage_bps: float = 0.0,
        max_volume_pct: float = 0.1,
    ):
        """
        Initialize backtest engine.

        :param gateway: DataGateway for fetching bars
        :param strategy: Trading strategy
        :param init_capital: Initial capital
        :param position_sizer: Position sizing strategy
        :param slippage_bps: Slippage in basis points
        :param max_volume_pct: Max fill as % of bar volume
        """
        self._gateway = gateway
        self._strategy = strategy
        self._init_capital = init_capital

        # Components
        self._portfolio = Portfolio(init_capital)
        self._manager = OrderManager()
        self._matching = DeterministicMatchingEngine(
            fill_at="close",
            max_volume_pct=max_volume_pct,
            slippage_bps=slippage_bps,
        )
        self._position_sizer = position_sizer or PercentSizer(equity_percent=0.10)

        # Trackers
        self._trade_tracker = TradeTracker()
        self._equity_tracker = EquityTracker()
        self._reports: list[dict] = []
        self._current_prices: dict[str, float] = {}

    def run(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> dict:
        """
        Run backtest for a single symbol.

        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :return: Backtest results dictionary
        """
        if not self._gateway.is_connected():
            raise RuntimeError("Gateway not connected. Call gateway.connect() first.")

        logger.info(f"Starting backtest: {symbol} from {start.date()} to {end.date()}")

        # Stream bars from gateway
        first_bar = True
        bar_count = 0

        for bar in self._gateway.stream_bars(symbol, timeframe, start, end):
            bar_count += 1
            self._matching.set_current_bar(bar)
            self._current_prices[symbol] = bar.close

            # Record initial equity on first bar
            if first_bar:
                self._equity_tracker.record_tick(bar.timestamp, self._portfolio.get_total_value())
                first_bar = False

            # Generate signal from strategy using MarketSnapshot
            snapshot = MarketSnapshot(
                timestamp=bar.timestamp,
                prices={bar.symbol: bar.close},
                bars={bar.symbol: bar},
            )
            signals = self._strategy.generate_signals(snapshot)
            signal = signals[0] if signals else None
            action = signal.get('action', 'HOLD') if signal else 'HOLD'

            # Process actionable signals (BUY/SELL)
            if signal is not None and action in ('BUY', 'SELL'):
                side = OrderSide.BUY if action == 'BUY' else OrderSide.SELL
                qty = self._position_sizer.calculate_qty(signal, self._portfolio, bar.close)
                if qty > 0:
                    self._process_order(bar, symbol, side, qty)

            # Update portfolio and record equity
            self._mark_to_market()
            self._equity_tracker.record_tick(bar.timestamp, self._portfolio.get_total_value())

        logger.info(f"Backtest complete: processed {bar_count} bars")

        return self._generate_results(symbol, start, end, bar_count)

    def run_multi(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> dict:
        """
        Run backtest for multiple symbols simultaneously.

        Fetches bars for all symbols, merges by timestamp, builds MarketSnapshot
        for each timestamp, and processes signals across all symbols.

        :param symbols: List of stock symbols
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :return: Backtest results dictionary
        """
        if not self._gateway.is_connected():
            raise RuntimeError("Gateway not connected. Call gateway.connect() first.")

        logger.info(f"Starting multi-symbol backtest: {symbols} from {start.date()} to {end.date()}")

        # Fetch all bars for all symbols
        all_bars: dict[str, list[Bar]] = {}
        for symbol in symbols:
            bars_list = list(self._gateway.stream_bars(symbol, timeframe, start, end))
            all_bars[symbol] = bars_list
            logger.info(f"  Loaded {len(bars_list)} bars for {symbol}")

        # Collect all unique timestamps and sort
        timestamps = sorted(set(
            bar.timestamp for bars in all_bars.values() for bar in bars
        ))

        if not timestamps:
            logger.warning("No bars found for any symbol")
            return self._generate_results_multi(symbols, start, end, 0)

        # Create index lookup for faster bar retrieval
        bar_index: dict[str, dict[datetime, Bar]] = {
            symbol: {bar.timestamp: bar for bar in bars}
            for symbol, bars in all_bars.items()
        }

        first_snapshot = True
        bar_count = 0

        for ts in timestamps:
            bar_count += 1

            # Build snapshot with all available prices at this timestamp
            prices: dict[str, float] = {}
            bars: dict[str, Bar] = {}

            for symbol in symbols:
                bar = bar_index[symbol].get(ts)
                if bar:
                    prices[symbol] = bar.close
                    bars[symbol] = bar
                    self._current_prices[symbol] = bar.close
                    self._matching.set_current_bar(bar)

            if not prices:
                continue  # Skip if no data for any symbol at this timestamp

            # Record initial equity on first snapshot
            if first_snapshot:
                self._equity_tracker.record_tick(ts, self._portfolio.get_total_value())
                first_snapshot = False

            # Build MarketSnapshot
            snapshot = MarketSnapshot(timestamp=ts, prices=prices, bars=bars)

            # Generate signals from strategy
            signals = self._strategy.generate_signals(snapshot)

            # Process each actionable signal
            for signal in signals:
                if signal is None:
                    continue
                action = signal.get('action', 'HOLD')
                symbol = signal.get('symbol')

                if action in ('BUY', 'SELL') and symbol and symbol in bars:
                    side = OrderSide.BUY if action == 'BUY' else OrderSide.SELL
                    bar = bars[symbol]
                    qty = self._position_sizer.calculate_qty(signal, self._portfolio, bar.close)
                    if qty > 0:
                        self._matching.set_current_bar(bar)
                        self._process_order(bar, symbol, side, qty)

            # Update portfolio and record equity
            self._mark_to_market()
            self._equity_tracker.record_tick(ts, self._portfolio.get_total_value())

        logger.info(f"Multi-symbol backtest complete: processed {bar_count} timestamps")

        return self._generate_results_multi(symbols, start, end, bar_count)

    def _generate_results_multi(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        bar_count: int,
    ) -> dict:
        """Generate backtest results summary for multi-symbol run."""
        equity_series = self._equity_tracker.get_equity_series()
        equity_curve = [
            {'timestamp': ts, 'value': val}
            for ts, val in zip(equity_series.index, equity_series.values)
        ] if not equity_series.empty else []

        final_value = self._portfolio.get_total_value()
        total_return = (final_value - self._init_capital) / self._init_capital * 100

        trades = self._trade_tracker.completed_trades

        return {
            'symbols': symbols,
            'start': start,
            'end': end,
            'bar_count': bar_count,
            'initial_capital': self._init_capital,
            'final_value': final_value,
            'total_return_pct': total_return,
            'total_trades': len(trades),
            'equity_curve': equity_curve,
            'trades': trades,
            'reports': self._reports,
        }

    def _process_order(
        self,
        bar: Bar,
        symbol: str,
        side: OrderSide,
        qty: float,
    ) -> None:
        """Process an order through validation and matching."""
        # Create order
        order = Order(
            symbol=symbol,
            qty=qty,
            price=bar.close,
            side=side,
            timestamp=bar.timestamp,
        )

        # Validate order
        is_valid = self._manager.validate_order(order, self._portfolio)
        if not is_valid:
            logger.debug(f"Order {order.order_id} blocked by OrderManager")
            return

        # Acknowledge and match
        order.transition(OrderState.ACKED)
        report = self._matching.match(order)
        self._reports.append(report)

        # Process fill
        status = report.get('status')
        filled_qty = report.get('filled_qty', 0.0)
        fill_price = report.get('fill_price', bar.close)

        if status in ['filled', 'partially_filled'] and filled_qty > 0:
            self._process_fill(symbol, side, filled_qty, fill_price, bar.timestamp, order.order_id)

    def _process_fill(
        self,
        symbol: str,
        side: OrderSide,
        filled_qty: float,
        fill_price: float,
        timestamp: datetime,
        order_id: int,
    ) -> None:
        """Process a fill: update portfolio and track trade."""
        side_mul = side.multiplier

        # Track trade
        self._trade_tracker.process_fill(
            symbol=symbol,
            side=side,
            filled_qty=filled_qty,
            fill_price=fill_price,
            timestamp=timestamp,
            order_id=order_id,
        )

        # Update cash
        cash_delta = -filled_qty * fill_price * side_mul
        self._portfolio.update_quantity("cash", cash_delta)

        # Update position
        try:
            position = Position(symbol, filled_qty, fill_price)
            self._portfolio.add_position(position, self._portfolio.root)
        except ValueError:
            # Position exists, update it
            existing = self._portfolio.get_position(symbol)[0]
            existing_qty = existing['quantity']
            existing_price = existing['price']

            total_qty = existing_qty + (filled_qty * side_mul)
            if total_qty != 0:
                new_avg_price = (existing_qty * existing_price + filled_qty * fill_price * side_mul) / total_qty
            else:
                new_avg_price = fill_price

            self._portfolio.update_quantity(symbol, filled_qty * side_mul)
            self._portfolio.update_price(symbol, abs(new_avg_price))

    def _mark_to_market(self) -> None:
        """Update positions to current market prices."""
        for pos in self._portfolio.get_positions():
            symbol = pos['symbol']
            if symbol == 'cash':
                continue
            if symbol in self._current_prices:
                self._portfolio.update_price(symbol, self._current_prices[symbol])

    def _generate_results(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        bar_count: int,
    ) -> dict:
        """Generate backtest results summary."""
        equity_series = self._equity_tracker.get_equity_series()
        equity_curve = [
            {'timestamp': ts, 'value': val}
            for ts, val in zip(equity_series.index, equity_series.values)
        ] if not equity_series.empty else []

        final_value = self._portfolio.get_total_value()
        total_return = (final_value - self._init_capital) / self._init_capital * 100

        trades = self._trade_tracker.completed_trades

        return {
            'symbol': symbol,
            'start': start,
            'end': end,
            'bar_count': bar_count,
            'initial_capital': self._init_capital,
            'final_value': final_value,
            'total_return_pct': total_return,
            'total_trades': len(trades),
            'equity_curve': equity_curve,
            'trades': trades,
            'reports': self._reports,
        }

    @property
    def portfolio(self) -> Portfolio:
        """Get the portfolio."""
        return self._portfolio

    @property
    def trade_tracker(self) -> TradeTracker:
        """Get the trade tracker."""
        return self._trade_tracker

    @property
    def equity_tracker(self) -> EquityTracker:
        """Get the equity tracker."""
        return self._equity_tracker
