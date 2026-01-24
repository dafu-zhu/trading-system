"""
Live Trading Engine - Orchestrates real-time trading.

Integrates strategy execution, risk management, and order execution for live trading.
Supports both paper trading (via Alpaca) and dry-run mode (historical replay).
"""

import logging
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from config.trading_config import LiveEngineConfig, DataType, SymbolConfig, AssetType
from gateway.alpaca_data_gateway import AlpacaDataGateway
from gateway.alpaca_trading_gateway import AlpacaTradingGateway
from models import (
    TradingGateway,
    Strategy,
    PositionSizer,
    MarketDataPoint,
    OrderSide,
    OrderType,
    Timeframe,
)
from orders.order_validator import OrderValidator
from risk.risk_manager import RiskManager, ExitSignal
from backtester.position_sizer import PercentSizer
from gateway.order_gateway import OrderGateway

logger = logging.getLogger(__name__)


@dataclass
class EngineMetrics:
    """Real-time engine metrics."""

    tick_count: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    stop_loss_triggered: int = 0
    signals_generated: int = 0
    start_time: Optional[datetime] = None
    last_tick_time: Optional[datetime] = None
    last_status_time: Optional[datetime] = None


@dataclass
class LivePosition:
    """Position tracking for live trading."""

    symbol: str
    quantity: float
    average_cost: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def update_price(self, price: float) -> None:
        """Update current price and unrealized P&L."""
        self.current_price = price
        self.unrealized_pnl = (price - self.average_cost) * self.quantity


class LiveTradingEngine:
    """
    Real-time trading engine for live execution.

    Workflow:
    1. Receives real-time market data via WebSocket or historical replay
    2. Passes data to strategy for signal generation
    3. Validates orders through OrderValidator (risk checks)
    4. Checks stop-loss conditions via RiskManager
    5. Submits valid orders to TradingGateway
    6. Tracks positions and P&L
    7. Logs all events for audit trail

    Example:
        config = LiveEngineConfig.from_yaml("config/live_trading.yaml")
        strategy = MACDStrategy(gateway, Timeframe.MIN_1)
        sizer = PercentSizer(0.10)

        engine = LiveTradingEngine(config, strategy, sizer)
        engine.run(symbols=["AAPL", "MSFT"])
    """

    def __init__(
        self,
        config: LiveEngineConfig,
        strategy: Strategy,
        position_sizer: Optional[PositionSizer] = None,
        data_gateway: Optional[AlpacaDataGateway] = None,
        trading_gateway: Optional[TradingGateway] = None,
    ):
        """
        Initialize live trading engine.

        Args:
            config: Engine configuration
            strategy: Trading strategy implementing Strategy interface
            position_sizer: Position sizing strategy (default: PercentSizer(0.10))
            data_gateway: Custom data gateway (default: AlpacaDataGateway)
            trading_gateway: Custom trading gateway (default: AlpacaTradingGateway)
        """
        self.config = config
        self.strategy = strategy
        self.position_sizer = position_sizer or PercentSizer(equity_percent=0.10)

        # Initialize gateways
        if data_gateway:
            self.data_gateway = data_gateway
        else:
            self.data_gateway = AlpacaDataGateway(
                api_key=config.trading.api_key,
                api_secret=config.trading.api_secret,
            )

        if trading_gateway:
            self.trading_gateway = trading_gateway
        elif not config.trading.dry_run:
            self.trading_gateway = AlpacaTradingGateway(
                api_key=config.trading.api_key,
                api_secret=config.trading.api_secret,
                base_url=config.trading.base_url,
            )
        else:
            self.trading_gateway = None  # Dry run mode

        # Initialize risk management
        self.order_validator = OrderValidator(config.risk)
        self.risk_manager: Optional[RiskManager] = None  # Initialized on run()

        # Portfolio state
        self.cash: float = 0.0
        self.initial_capital: float = 0.0
        self.positions: dict[str, LivePosition] = {}
        self.current_prices: dict[str, float] = {}

        # Engine state
        self.running: bool = False
        self.metrics = EngineMetrics()
        self._shutdown_requested: bool = False
        self._last_signals: dict[str, str] = {}  # Track last signal per symbol to avoid duplicates

        # Order gateway for logging
        if config.log_orders:
            self.order_gateway: Optional[OrderGateway] = OrderGateway(
                log_file=config.order_log_path,
                append=True,
                dry_run_prefix=config.trading.dry_run,
            )
        else:
            self.order_gateway = None

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(
            "LiveTradingEngine initialized: mode=%s, trading=%s, stop_loss=%s",
            "DRY_RUN" if config.trading.dry_run else ("PAPER" if config.trading.paper_mode else "LIVE"),
            "ENABLED" if config.enable_trading else "DISABLED",
            "ENABLED" if config.enable_stop_loss else "DISABLED",
        )

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.warning("Received signal %d. Shutting down gracefully...", signum)
        self._shutdown_requested = True
        self.stop()

    def _get_positions_dict(self) -> dict[str, dict]:
        """Convert positions to dict format for RiskManager/OrderValidator."""
        return {
            symbol: {
                "quantity": pos.quantity,
                "price": pos.average_cost,
            }
            for symbol, pos in self.positions.items()
            if pos.quantity != 0
        }

    def _get_portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        position_value = sum(
            pos.quantity * pos.current_price
            for pos in self.positions.values()
            if pos.quantity != 0
        )
        return self.cash + position_value

    def _resolve_symbol_configs(self, symbols: list[str]) -> list[SymbolConfig]:
        """
        Convert symbol strings to SymbolConfig with proper asset_type.

        Args:
            symbols: List of symbol strings

        Returns:
            List of SymbolConfig objects with asset_type set
        """
        symbol_configs = []
        for sym in symbols:
            if isinstance(sym, SymbolConfig):
                symbol_configs.append(sym)
            else:
                # Check if symbol is in config
                config_sym = next(
                    (s for s in self.config.symbols if s.symbol == sym),
                    None
                )
                if config_sym:
                    symbol_configs.append(config_sym)
                else:
                    # Auto-detect: crypto symbols contain "/"
                    asset_type = AssetType.CRYPTO if "/" in sym else AssetType.STOCK
                    symbol_configs.append(SymbolConfig(symbol=sym, asset_type=asset_type))
        return symbol_configs

    def _on_market_data(self, tick: MarketDataPoint) -> None:
        """
        Handle incoming market data tick.

        Args:
            tick: Market data point from streaming
        """
        try:
            self.metrics.tick_count += 1
            self.metrics.last_tick_time = tick.timestamp

            # Log tick at debug level
            logger.debug(
                "[%s] %s: $%.4f (vol: %.2f)",
                tick.timestamp.strftime("%H:%M:%S"),
                tick.symbol,
                tick.price,
                tick.volume or 0,
            )

            # Update current prices
            self.current_prices[tick.symbol] = tick.price

            # Update position unrealized P&L
            if tick.symbol in self.positions:
                self.positions[tick.symbol].update_price(tick.price)

            # Check stop-loss conditions first
            if self.config.enable_stop_loss and self.risk_manager:
                exit_signals = self.risk_manager.check_stops(
                    self.current_prices,
                    self._get_portfolio_value(),
                    self._get_positions_dict(),
                )

                # Execute stop-loss orders immediately
                for exit_signal in exit_signals:
                    logger.warning(
                        "STOP-LOSS TRIGGERED for %s: %s",
                        exit_signal.symbol,
                        exit_signal.reason,
                    )
                    self._execute_exit_signal(exit_signal, tick.timestamp)
                    self.metrics.stop_loss_triggered += 1

            # If circuit breaker triggered, don't generate new signals
            if self.risk_manager and self.risk_manager.circuit_breaker_triggered:
                self._maybe_log_status()
                if self.metrics.tick_count % 100 == 0:
                    logger.warning("CIRCUIT BREAKER ACTIVE - Trading halted")
                return

            # Generate strategy signals
            signals = self.strategy.generate_signals(tick)

            if signals:
                for signal_dict in signals:
                    action = signal_dict.get("action", "HOLD")
                    symbol = signal_dict.get("symbol", tick.symbol)

                    # Skip if same signal as last time (avoid duplicate orders)
                    last_signal = self._last_signals.get(symbol)
                    if action == last_signal:
                        continue  # Signal unchanged, skip

                    # Update last signal
                    self._last_signals[symbol] = action

                    if action in ("BUY", "SELL"):
                        self.metrics.signals_generated += 1
                        logger.info(
                            "SIGNAL: %s %s @ $%.4f",
                            action,
                            symbol,
                            signal_dict.get("price", tick.price),
                        )
                        self._process_signal(signal_dict, tick)

            # Time-based status logging (every 30 seconds)
            self._maybe_log_status()

        except Exception as e:
            logger.exception("Error processing market data: %s", e)

    def _maybe_log_status(self) -> None:
        """Log status if enough time has passed (every 30 seconds)."""
        now = datetime.now()
        if self.metrics.last_status_time is None:
            self.metrics.last_status_time = now
            self._log_status()
        elif (now - self.metrics.last_status_time).total_seconds() >= 30:
            self.metrics.last_status_time = now
            self._log_status()

    def _process_signal(self, signal_dict: dict, tick: MarketDataPoint) -> None:
        """
        Process a trading signal.

        Args:
            signal_dict: Signal from strategy
            tick: Current market data
        """
        symbol = signal_dict.get("symbol", tick.symbol)
        action = signal_dict["action"]
        price = signal_dict.get("price", tick.price)

        # Determine order side
        if action == "BUY":
            side = OrderSide.BUY
        elif action == "SELL":
            side = OrderSide.SELL
        else:
            return

        # Calculate quantity
        if side == OrderSide.SELL and symbol in self.positions:
            # SELL: use actual position quantity
            quantity = self.positions[symbol].quantity
        else:
            # BUY: use position sizer
            outer_self = self
            class MockPortfolio:
                def get_total_value(self):
                    return outer_self._get_portfolio_value()
            quantity = self.position_sizer.calculate_qty(signal_dict, MockPortfolio(), price)

        if quantity and quantity <= 0:
            logger.debug("Position sizer returned 0 quantity for %s", symbol)
            return

        # Validate order
        result = self.order_validator.validate(
            symbol=symbol,
            side=side,
            quantity=float(quantity or 0),
            price=price,
            cash=self.cash,
            positions=self._get_positions_dict(),
            current_prices=self.current_prices,
        )

        if not result.is_valid:
            logger.info(
                "Order REJECTED for %s: %s",
                symbol,
                result.error_message,
            )
            self.metrics.orders_rejected += 1
            # Log rejection
            if self.order_gateway:
                self.order_gateway.log_order_rejected(
                    order_id=f"val_{self.metrics.orders_rejected}",
                    symbol=symbol,
                    side=side.value,
                    order_type="market",
                    quantity=float(quantity or 0),
                    price=price,
                    reason=result.error_message,
                )
            return

        # Execute order
        self._execute_order(
            symbol=symbol,
            side=side,
            quantity=float(quantity or 0),
            price=price,
            timestamp=tick.timestamp,
        )

    def _execute_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        timestamp: datetime,
    ) -> None:
        """
        Execute an order.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            price: Expected price
            timestamp: Order timestamp
        """
        self.metrics.orders_submitted += 1

        if self.config.enable_trading and self.trading_gateway:
            # Submit to broker
            try:
                result = self.trading_gateway.submit_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=OrderType.MARKET,
                )

                logger.info(
                    "Order SUBMITTED: %s %.2f %s @ MARKET (order_id=%s)",
                    side.value,
                    quantity,
                    symbol,
                    result.order_id,
                )

                # Log order sent
                if self.order_gateway:
                    self.order_gateway.log_order_sent(
                        order_id=result.order_id,
                        symbol=symbol,
                        side=side.value,
                        order_type="market",
                        quantity=quantity,
                        price=price,
                    )

                # Record for rate limiting
                self.order_validator.record_order(symbol, result.order_id)

                # Check if order was accepted
                if not result.order_id or result.status == "rejected":
                    # Order failed at API level (e.g., insufficient balance)
                    raise ValueError(result.message or "Order rejected by broker")

                # Wait for fill
                if result.status == "filled":
                    self._process_fill(
                        symbol=symbol,
                        side=side,
                        quantity=result.filled_quantity,
                        price=result.filled_avg_price or price,
                        timestamp=timestamp,
                    )
                else:
                    # Poll for fill (simplified)
                    self._wait_for_fill(result.order_id, symbol, side, quantity, price, timestamp)

            except Exception as e:
                logger.error("Order FAILED for %s: %s", symbol, e)
                self.metrics.orders_rejected += 1
                # Log rejection
                if self.order_gateway:
                    self.order_gateway.log_order_rejected(
                        order_id=f"failed_{self.metrics.orders_submitted}",
                        symbol=symbol,
                        side=side.value,
                        order_type="market",
                        quantity=quantity,
                        price=price,
                        reason=str(e),
                    )

        else:
            # Dry run - simulate fill
            dry_run_order_id = f"dry_{self.metrics.orders_submitted}"
            logger.info(
                "DRY RUN: %s %.2f %s @ %.2f",
                side.value,
                quantity,
                symbol,
                price,
            )
            # Log dry run order
            if self.order_gateway:
                self.order_gateway.log_order_sent(
                    order_id=dry_run_order_id,
                    symbol=symbol,
                    side=side.value,
                    order_type="market",
                    quantity=quantity,
                    price=price,
                    message="DRY_RUN",
                )
            self._process_fill(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )

    def _execute_exit_signal(self, exit_signal: ExitSignal, timestamp: datetime) -> None:
        """Execute a stop-loss exit signal."""
        self._execute_order(
            symbol=exit_signal.symbol,
            side=exit_signal.side,
            quantity=exit_signal.quantity,
            price=exit_signal.trigger_price,
            timestamp=timestamp,
        )

    def _wait_for_fill(
        self,
        order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        timestamp: datetime,
        timeout: int = 10,
    ) -> None:
        """Wait for order fill with timeout."""
        if not self.trading_gateway:
            return

        start_time = time.time()

        while time.time() - start_time < timeout:
            result = self.trading_gateway.get_order(order_id)
            if result is None:
                break

            if result.status == "filled":
                self._process_fill(
                    symbol=symbol,
                    side=side,
                    quantity=result.filled_quantity,
                    price=result.filled_avg_price or price,
                    timestamp=timestamp,
                )
                return

            elif result.status in ("canceled", "rejected", "expired"):
                logger.warning("Order %s for %s", result.status.upper(), symbol)
                return

            time.sleep(0.5)

        logger.warning("Timeout waiting for order fill: %s", order_id)

    def _process_fill(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        timestamp: datetime,
    ) -> None:
        """
        Process an order fill.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Filled quantity
            price: Fill price
            timestamp: Fill timestamp
        """
        self.metrics.orders_filled += 1

        # Update position
        if symbol not in self.positions:
            self.positions[symbol] = LivePosition(
                symbol=symbol,
                quantity=0,
                average_cost=0,
                current_price=price,
            )

        pos = self.positions[symbol]

        if side == OrderSide.BUY:
            # Update average cost
            total_cost = pos.average_cost * pos.quantity + price * quantity
            pos.quantity += quantity
            if pos.quantity > 0:
                pos.average_cost = total_cost / pos.quantity
            self.cash -= price * quantity

            # Add stop-loss for new position
            if self.config.enable_stop_loss and self.risk_manager:
                self.risk_manager.add_position_stop(
                    symbol=symbol,
                    entry_price=price,
                    quantity=quantity,
                )

        else:  # SELL
            # Calculate realized P&L
            if pos.quantity > 0:
                realized_pnl = (price - pos.average_cost) * min(quantity, pos.quantity)
                pos.realized_pnl += realized_pnl

            pos.quantity -= quantity
            self.cash += price * quantity

            # Remove stop if position closed
            if pos.quantity <= 0 and self.risk_manager:
                self.risk_manager.remove_position_stop(symbol)

        pos.update_price(price)

        logger.info(
            "FILLED: %s %.2f %s @ %.2f (position: %.2f)",
            side.value,
            quantity,
            symbol,
            price,
            pos.quantity,
        )

        # Log fill to order gateway
        if self.order_gateway:
            self.order_gateway.log_order_filled(
                order_id=f"fill_{self.metrics.orders_filled}",
                symbol=symbol,
                filled_qty=quantity,
                avg_price=price,
            )

    def _log_status(self) -> None:
        """Log current engine status."""
        portfolio_value = self._get_portfolio_value()
        pnl = portfolio_value - self.initial_capital
        pnl_pct = (pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0
        active_positions = len([p for p in self.positions.values() if p.quantity != 0])

        # Format prices
        price_strs = [f"{sym}=${p:.2f}" for sym, p in self.current_prices.items()]
        prices_display = ", ".join(price_strs) if price_strs else "none"

        # Calculate runtime
        runtime = ""
        if self.metrics.start_time:
            elapsed = datetime.now() - self.metrics.start_time
            mins, secs = divmod(int(elapsed.total_seconds()), 60)
            runtime = f"{mins}m{secs}s"

        logger.info(
            "STATUS | ticks:%d | signals:%d | orders:%d/%d | "
            "positions:%d | P&L:$%.2f (%.2f%%) | prices:[%s] | runtime:%s",
            self.metrics.tick_count,
            self.metrics.signals_generated,
            self.metrics.orders_filled,
            self.metrics.orders_submitted,
            active_positions,
            pnl,
            pnl_pct,
            prices_display,
            runtime,
        )

    def _sync_positions(self) -> None:
        """Sync existing positions from broker."""
        if not self.trading_gateway:
            return

        try:
            account = self.trading_gateway.get_account()
            self.cash = account.cash
            self.initial_capital = account.portfolio_value

            positions = self.trading_gateway.get_positions()
            if positions:
                logger.info("Syncing %d existing positions from broker...", len(positions))
                for pos_info in positions:
                    symbol = pos_info.symbol
                    self.positions[symbol] = LivePosition(
                        symbol=symbol,
                        quantity=pos_info.quantity,
                        average_cost=pos_info.avg_entry_price,
                        current_price=pos_info.avg_entry_price,
                    )

                    # Add stop-loss for existing positions
                    if self.config.enable_stop_loss and self.risk_manager:
                        self.risk_manager.add_position_stop(
                            symbol=symbol,
                            entry_price=pos_info.avg_entry_price,
                            quantity=pos_info.quantity,
                        )

                    logger.info(
                        "  %s: %.2f @ $%.2f",
                        symbol,
                        pos_info.quantity,
                        pos_info.avg_entry_price,
                    )

        except Exception as e:
            logger.error("Failed to sync positions: %s", e)

    def run(
        self,
        symbols: list[str],
        data_type: Optional[DataType] = None,
        replay_start: Optional[datetime] = None,
        replay_end: Optional[datetime] = None,
        replay_timeframe: Timeframe = Timeframe.MIN_1,
    ) -> None:
        """
        Start live trading.

        Args:
            symbols: List of symbols to trade
            data_type: Type of market data (default: from config)
            replay_start: For dry-run, start of historical replay
            replay_end: For dry-run, end of historical replay
            replay_timeframe: For dry-run, timeframe of historical data

        Note: This is a blocking call. Press Ctrl+C to stop.
        """
        data_type = data_type or self.config.data_type

        # Connect gateways
        if not self.data_gateway.connect():
            raise RuntimeError("Failed to connect to data gateway")

        if self.trading_gateway and not self.trading_gateway.connect():
            raise RuntimeError("Failed to connect to trading gateway")

        # Initialize capital
        if self.trading_gateway:
            self._sync_positions()
        else:
            # Dry run defaults
            self.cash = 100_000.0
            self.initial_capital = 100_000.0

        # Initialize risk manager
        self.risk_manager = RiskManager(
            self.config.stop_loss,
            initial_portfolio_value=self.initial_capital,
        )

        # Log startup
        logger.info("=" * 60)
        logger.info("LIVE TRADING ENGINE")
        logger.info("=" * 60)
        mode = "DRY_RUN" if self.config.trading.dry_run else (
            "PAPER" if self.config.trading.paper_mode else "LIVE"
        )
        logger.info("Mode: %s", mode)
        logger.info("Trading: %s", "ENABLED" if self.config.enable_trading else "DISABLED")
        logger.info("Stop-Loss: %s", "ENABLED" if self.config.enable_stop_loss else "DISABLED")
        logger.info("Strategy: %s", self.strategy.__class__.__name__)
        logger.info("Symbols: %s", ", ".join(symbols))
        logger.info("Data Type: %s", data_type.value)
        logger.info("Initial Capital: $%.2f", self.initial_capital)
        logger.info("=" * 60)

        self.metrics.start_time = datetime.now()
        self.running = True
        self._shutdown_requested = False

        try:
            # Convert symbols to SymbolConfig with proper asset_type
            symbol_configs = self._resolve_symbol_configs(symbols)

            if self.config.trading.dry_run and replay_start and replay_end:
                # Historical replay mode
                logger.info("Starting historical replay from %s to %s...", replay_start, replay_end)
                self.data_gateway.replay_historical(
                    symbols=symbol_configs,
                    callback=self._on_market_data,
                    timeframe=replay_timeframe,
                    start=replay_start,
                    end=replay_end,
                    speed=0,  # Instant replay
                )
            else:
                # Real-time streaming
                logger.info("Starting market data stream...")
                logger.info("Press Ctrl+C to stop\n")

                self.data_gateway.stream_realtime(
                    symbols=symbol_configs,
                    callback=self._on_market_data,
                    data_type=data_type,
                )

        except KeyboardInterrupt:
            logger.warning("Keyboard interrupt received")
        except Exception as e:
            logger.exception("Fatal error: %s", e)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop live trading and clean up."""
        if not self.running:
            return

        logger.info("=" * 60)
        logger.info("SHUTTING DOWN")
        logger.info("=" * 60)

        self.running = False

        # Close all positions if configured
        if self.config.close_positions_on_exit:
            self._close_all_positions()

        # Stop streaming
        if hasattr(self.data_gateway, 'stop_streaming'):
            self.data_gateway.stop_streaming()

        # Disconnect gateways
        self.data_gateway.disconnect()
        if self.trading_gateway:
            self.trading_gateway.disconnect()

        # Final metrics
        duration = (
            (datetime.now() - self.metrics.start_time).total_seconds()
            if self.metrics.start_time
            else 0
        )
        portfolio_value = self._get_portfolio_value()
        pnl = portfolio_value - self.initial_capital
        pnl_pct = (pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0

        logger.info("FINAL PERFORMANCE:")
        logger.info("  Duration: %.1f seconds", duration)
        logger.info("  Ticks processed: %d", self.metrics.tick_count)
        logger.info("  Orders submitted: %d", self.metrics.orders_submitted)
        logger.info("  Orders filled: %d", self.metrics.orders_filled)
        logger.info("  Orders rejected: %d", self.metrics.orders_rejected)
        logger.info("  Stop-loss triggered: %d", self.metrics.stop_loss_triggered)
        logger.info("  Final Value: $%.2f", portfolio_value)
        logger.info("  P&L: $%.2f (%.2f%%)", pnl, pnl_pct)

        # Log open positions
        open_positions = [p for p in self.positions.values() if p.quantity != 0]
        if open_positions:
            logger.info("OPEN POSITIONS:")
            for pos in open_positions:
                logger.info(
                    "  %s: %.2f @ $%.2f (P&L: $%.2f)",
                    pos.symbol,
                    pos.quantity,
                    pos.average_cost,
                    pos.unrealized_pnl + pos.realized_pnl,
                )

        logger.info("=" * 60)
        logger.info("Shutdown complete")

    def _close_all_positions(self) -> None:
        """Close all open positions on shutdown."""
        if not self.trading_gateway:
            return

        open_positions = [p for p in self.positions.values() if p.quantity > 0]
        if not open_positions:
            logger.info("No open positions to close")
            return

        logger.info("Closing %d open position(s)...", len(open_positions))

        for pos in open_positions:
            try:
                # Determine side (sell to close long, buy to close short)
                side = OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY
                quantity = abs(pos.quantity)

                result = self.trading_gateway.submit_order(
                    symbol=pos.symbol,
                    side=side,
                    quantity=quantity,
                    order_type=OrderType.MARKET,
                )

                if result.order_id:
                    logger.info(
                        "Closed %s: %s %.4f @ MARKET (order_id=%s)",
                        pos.symbol,
                        side.value,
                        quantity,
                        result.order_id,
                    )
                else:
                    logger.error("Failed to close %s: %s", pos.symbol, result.message)

            except Exception as e:
                logger.error("Error closing position %s: %s", pos.symbol, e)

    def __repr__(self) -> str:
        status = "RUNNING" if self.running else "STOPPED"
        return f"LiveTradingEngine(status={status}, ticks={self.metrics.tick_count})"
