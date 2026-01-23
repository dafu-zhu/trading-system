"""
Risk Manager - Implements stop-loss and risk control mechanisms.

Provides multiple types of stop-loss protection:
- Position-level stops (fixed %, trailing %)
- Portfolio-level stops (max daily loss, max drawdown)
- Circuit breakers (pause trading on unusual conditions)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import logging

from config.trading_config import StopLossConfig
from models import OrderSide, OrderType

logger = logging.getLogger(__name__)


class StopType(Enum):
    """Types of stop-loss orders."""

    FIXED_PERCENT = "fixed_percent"
    TRAILING_PERCENT = "trailing_percent"
    ABSOLUTE_PRICE = "absolute_price"


@dataclass
class PositionStop:
    """
    Tracks stop-loss information for a position.

    Attributes:
        symbol: Asset symbol
        entry_price: Price at which position was entered
        stop_price: Current stop price level
        highest_price: Highest price seen (for trailing stops)
        lowest_price: Lowest price seen (for short trailing stops)
        stop_type: Type of stop loss
        quantity: Position size (positive for long, negative for short)
    """

    symbol: str
    entry_price: float
    stop_price: float
    highest_price: float
    lowest_price: float
    stop_type: StopType
    quantity: float


@dataclass
class ExitSignal:
    """
    Signal to exit a position due to stop-loss trigger.

    Attributes:
        symbol: Asset symbol
        side: Order side (SELL for long, BUY for short)
        quantity: Number of shares/coins to exit
        order_type: Always MARKET for stop exits
        reason: Reason for exit
        trigger_price: Price that triggered the stop
        stop_price: The stop price that was breached
    """

    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    reason: str
    trigger_price: float
    stop_price: float


class RiskManager:
    """
    Manages stop-loss orders and portfolio risk controls.

    Features:
    - Position-level stop losses (fixed or trailing)
    - Portfolio-level circuit breakers
    - Automatic exit signal generation when stops triggered
    - Tracks high water marks for trailing stops and drawdown

    Example:
        config = StopLossConfig(position_stop_pct=2.0, use_trailing_stops=True)
        risk_mgr = RiskManager(config, initial_portfolio_value=100_000)

        # Add stop for new position
        risk_mgr.add_position_stop(symbol="AAPL", entry_price=150.0, quantity=100)

        # Check stops on price update
        exit_signals = risk_mgr.check_stops(
            current_prices={"AAPL": 147.0},
            portfolio_value=98_000,
            positions={"AAPL": {"quantity": 100, "price": 150.0}}
        )

        # Execute exit orders if any
        for signal in exit_signals:
            execute_order(signal)
    """

    def __init__(self, config: StopLossConfig, initial_portfolio_value: float):
        """
        Initialize risk manager.

        Args:
            config: Stop-loss configuration
            initial_portfolio_value: Starting portfolio value for circuit breaker
        """
        self.config = config
        self.initial_portfolio_value = initial_portfolio_value
        self.daily_start_value = initial_portfolio_value
        self.high_water_mark = initial_portfolio_value

        # Track stops for each position
        self.position_stops: dict[str, PositionStop] = {}

        # Circuit breaker state
        self.circuit_breaker_triggered = False
        self.circuit_breaker_time: Optional[datetime] = None
        self.circuit_breaker_reason: Optional[str] = None

        logger.info(
            "RiskManager initialized: position_stop=%.1f%%, trailing=%.1f%%, "
            "portfolio_stop=%.1f%%, max_drawdown=%.1f%%",
            config.position_stop_pct,
            config.trailing_stop_pct,
            config.portfolio_stop_pct,
            config.max_drawdown_pct,
        )

    def add_position_stop(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        stop_type: Optional[StopType] = None,
    ) -> PositionStop:
        """
        Add or update stop-loss for a position.

        Args:
            symbol: Asset symbol
            entry_price: Entry price for position
            quantity: Position size (positive for long, negative for short)
            stop_type: Type of stop (default: uses config settings)

        Returns:
            The created PositionStop object
        """
        if stop_type is None:
            stop_type = (
                StopType.TRAILING_PERCENT
                if self.config.use_trailing_stops
                else StopType.FIXED_PERCENT
            )

        # Calculate initial stop price
        stop_pct = (
            self.config.trailing_stop_pct
            if stop_type == StopType.TRAILING_PERCENT
            else self.config.position_stop_pct
        )

        if quantity > 0:  # Long position
            stop_price = entry_price * (1 - stop_pct / 100)
        else:  # Short position
            stop_price = entry_price * (1 + stop_pct / 100)

        position_stop = PositionStop(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            highest_price=entry_price,
            lowest_price=entry_price,
            stop_type=stop_type,
            quantity=quantity,
        )

        self.position_stops[symbol] = position_stop

        logger.debug(
            "Added stop for %s: entry=%.2f, stop=%.2f, type=%s",
            symbol,
            entry_price,
            stop_price,
            stop_type.value,
        )

        return position_stop

    def remove_position_stop(self, symbol: str) -> None:
        """
        Remove stop-loss tracking for a position.

        Args:
            symbol: Asset symbol
        """
        if symbol in self.position_stops:
            del self.position_stops[symbol]
            logger.debug("Removed stop for %s", symbol)

    def update_position_quantity(self, symbol: str, new_quantity: float) -> None:
        """
        Update position quantity for a tracked stop.

        Args:
            symbol: Asset symbol
            new_quantity: New position quantity
        """
        if symbol in self.position_stops:
            self.position_stops[symbol].quantity = new_quantity
            if new_quantity == 0:
                self.remove_position_stop(symbol)

    def check_stops(
        self,
        current_prices: dict[str, float],
        portfolio_value: float,
        positions: dict[str, dict],
    ) -> list[ExitSignal]:
        """
        Check all stop-loss conditions and generate exit signals if triggered.

        Args:
            current_prices: Current market prices by symbol
            portfolio_value: Current total portfolio value
            positions: Current positions as dict of {symbol: {"quantity": float, "price": float}}

        Returns:
            List of exit signals (empty if no stops triggered)
        """
        exit_signals: list[ExitSignal] = []

        # Check circuit breaker first
        circuit_triggered, reason = self._check_circuit_breaker(portfolio_value)
        if circuit_triggered:
            logger.warning("Circuit breaker triggered: %s", reason)
            return self._generate_exit_all_signals(positions, current_prices, reason)

        # Check individual position stops
        for symbol, pos_info in positions.items():
            quantity = pos_info.get("quantity", 0)
            if quantity == 0:
                continue

            if symbol not in current_prices:
                continue

            # Auto-add stop for positions without explicit stop
            if symbol not in self.position_stops:
                entry_price = pos_info.get("price", current_prices[symbol])
                self.add_position_stop(
                    symbol=symbol,
                    entry_price=entry_price,
                    quantity=quantity,
                )

            current_price = current_prices[symbol]
            stop = self.position_stops[symbol]

            # Update trailing stop if applicable
            if stop.stop_type == StopType.TRAILING_PERCENT:
                self._update_trailing_stop(stop, current_price)

            # Check if stop triggered
            if self._is_stop_triggered(stop, current_price):
                exit_signal = ExitSignal(
                    symbol=symbol,
                    side=OrderSide.SELL if quantity > 0 else OrderSide.BUY,
                    quantity=abs(quantity),
                    order_type=OrderType.MARKET,
                    reason=f"Stop-loss triggered ({stop.stop_type.value})",
                    trigger_price=current_price,
                    stop_price=stop.stop_price,
                )
                exit_signals.append(exit_signal)

                logger.warning(
                    "Stop triggered for %s: price=%.2f, stop=%.2f, reason=%s",
                    symbol,
                    current_price,
                    stop.stop_price,
                    exit_signal.reason,
                )

                # Remove stop (will be re-added if position re-entered)
                self.remove_position_stop(symbol)

        return exit_signals

    def _check_circuit_breaker(self, portfolio_value: float) -> tuple[bool, str]:
        """
        Check if portfolio-level circuit breaker should trigger.

        Args:
            portfolio_value: Current portfolio value

        Returns:
            Tuple of (triggered, reason)
        """
        if not self.config.enable_circuit_breaker:
            return False, ""

        if self.circuit_breaker_triggered:
            return True, self.circuit_breaker_reason or "Circuit breaker active"

        # Update high water mark
        if portfolio_value > self.high_water_mark:
            self.high_water_mark = portfolio_value

        # Check daily loss limit
        if self.daily_start_value > 0:
            daily_loss_pct = (
                (self.daily_start_value - portfolio_value)
                / self.daily_start_value
                * 100
            )
            if daily_loss_pct >= self.config.portfolio_stop_pct:
                self.circuit_breaker_triggered = True
                self.circuit_breaker_time = datetime.now()
                self.circuit_breaker_reason = f"Daily loss {daily_loss_pct:.1f}% >= {self.config.portfolio_stop_pct}%"
                return True, self.circuit_breaker_reason

        # Check max drawdown
        if self.high_water_mark > 0:
            drawdown_pct = (
                (self.high_water_mark - portfolio_value) / self.high_water_mark * 100
            )
            if drawdown_pct >= self.config.max_drawdown_pct:
                self.circuit_breaker_triggered = True
                self.circuit_breaker_time = datetime.now()
                self.circuit_breaker_reason = f"Max drawdown {drawdown_pct:.1f}% >= {self.config.max_drawdown_pct}%"
                return True, self.circuit_breaker_reason

        return False, ""

    def _update_trailing_stop(self, stop: PositionStop, current_price: float) -> None:
        """
        Update trailing stop price if position is profitable.

        Args:
            stop: Position stop to update
            current_price: Current market price
        """
        if stop.quantity > 0:  # Long position
            if current_price > stop.highest_price:
                stop.highest_price = current_price
                new_stop = current_price * (1 - self.config.trailing_stop_pct / 100)
                if new_stop > stop.stop_price:
                    old_stop = stop.stop_price
                    stop.stop_price = new_stop
                    logger.debug(
                        "Trailing stop raised for %s: %.2f -> %.2f (price=%.2f)",
                        stop.symbol,
                        old_stop,
                        new_stop,
                        current_price,
                    )
        else:  # Short position
            if current_price < stop.lowest_price:
                stop.lowest_price = current_price
                new_stop = current_price * (1 + self.config.trailing_stop_pct / 100)
                if new_stop < stop.stop_price:
                    old_stop = stop.stop_price
                    stop.stop_price = new_stop
                    logger.debug(
                        "Trailing stop lowered for %s: %.2f -> %.2f (price=%.2f)",
                        stop.symbol,
                        old_stop,
                        new_stop,
                        current_price,
                    )

    def _is_stop_triggered(self, stop: PositionStop, current_price: float) -> bool:
        """
        Check if stop-loss is triggered.

        Args:
            stop: Position stop configuration
            current_price: Current market price

        Returns:
            True if stop triggered
        """
        if stop.quantity > 0:  # Long position
            return current_price <= stop.stop_price
        else:  # Short position
            return current_price >= stop.stop_price

    def _generate_exit_all_signals(
        self,
        positions: dict[str, dict],
        current_prices: dict[str, float],
        reason: str,
    ) -> list[ExitSignal]:
        """
        Generate market orders to exit all positions (circuit breaker).

        Args:
            positions: All current positions
            current_prices: Current market prices
            reason: Reason for circuit breaker

        Returns:
            List of exit signals
        """
        exit_signals: list[ExitSignal] = []

        for symbol, pos_info in positions.items():
            quantity = pos_info.get("quantity", 0)
            if quantity == 0:
                continue

            current_price = current_prices.get(symbol, pos_info.get("price", 0))

            exit_signal = ExitSignal(
                symbol=symbol,
                side=OrderSide.SELL if quantity > 0 else OrderSide.BUY,
                quantity=abs(quantity),
                order_type=OrderType.MARKET,
                reason=f"Circuit breaker: {reason}",
                trigger_price=current_price,
                stop_price=0.0,  # N/A for circuit breaker
            )
            exit_signals.append(exit_signal)

            logger.warning(
                "Circuit breaker exit for %s: qty=%.2f, price=%.2f",
                symbol,
                quantity,
                current_price,
            )

            # Remove position stop
            self.remove_position_stop(symbol)

        return exit_signals

    def reset_daily_tracking(self, current_portfolio_value: float) -> None:
        """
        Reset daily tracking (call at start of trading day).

        Args:
            current_portfolio_value: Portfolio value at start of day
        """
        self.daily_start_value = current_portfolio_value
        logger.info("Daily tracking reset: start_value=%.2f", current_portfolio_value)

    def reset_circuit_breaker(self) -> None:
        """
        Reset circuit breaker (use with caution).

        Only reset if you're certain you want to resume trading after a stop.
        """
        self.circuit_breaker_triggered = False
        self.circuit_breaker_time = None
        self.circuit_breaker_reason = None
        logger.warning("Circuit breaker reset manually")

    def get_stop(self, symbol: str) -> Optional[PositionStop]:
        """Get the stop configuration for a symbol."""
        return self.position_stops.get(symbol)

    def get_all_stops(self) -> dict[str, PositionStop]:
        """Get all active position stops."""
        return self.position_stops.copy()

    def get_status(self) -> dict:
        """
        Get current risk manager status.

        Returns:
            Dictionary with status information
        """
        return {
            "circuit_breaker_triggered": self.circuit_breaker_triggered,
            "circuit_breaker_time": self.circuit_breaker_time,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "num_active_stops": len(self.position_stops),
            "high_water_mark": self.high_water_mark,
            "daily_start_value": self.daily_start_value,
            "active_stops": {
                symbol: {
                    "entry_price": stop.entry_price,
                    "stop_price": stop.stop_price,
                    "highest_price": stop.highest_price,
                    "stop_type": stop.stop_type.value,
                    "quantity": stop.quantity,
                }
                for symbol, stop in self.position_stops.items()
            },
            "config": {
                "position_stop_pct": self.config.position_stop_pct,
                "trailing_stop_pct": self.config.trailing_stop_pct,
                "portfolio_stop_pct": self.config.portfolio_stop_pct,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "use_trailing_stops": self.config.use_trailing_stops,
                "enable_circuit_breaker": self.config.enable_circuit_breaker,
            },
        }

    def __repr__(self) -> str:
        status = "TRIGGERED" if self.circuit_breaker_triggered else "ACTIVE"
        return (
            f"RiskManager(status={status}, "
            f"active_stops={len(self.position_stops)}, "
            f"position_stop={self.config.position_stop_pct}%)"
        )
