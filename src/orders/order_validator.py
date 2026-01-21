"""
Order Validator - Validates orders against risk limits before execution.

Checks:
1. Rate limits (global and per-symbol)
2. Capital sufficiency (cash minus buffer)
3. Position limits (size and value)
4. Total exposure limits
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

from config.trading_config import RiskConfig
from models import OrderSide

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    Result of order validation.

    Attributes:
        is_valid: True if order passes all checks
        error_code: Short error code (e.g., "RATE_LIMIT", "INSUFFICIENT_CAPITAL")
        error_message: Detailed error description
        check_failed: Name of the check that failed (if any)
    """

    is_valid: bool
    error_code: str = ""
    error_message: str = ""
    check_failed: str = ""


class OrderValidator:
    """
    Validates orders against risk limits before submission.

    Performs risk checks:
    - Rate limits: Prevent order spam (global and per-symbol)
    - Capital: Ensure sufficient cash for buy orders
    - Position limits: Prevent excessive concentration
    - Total exposure: Limit total portfolio risk

    Example:
        config = RiskConfig(max_position_size=500)
        validator = OrderValidator(config)

        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0,
            cash=10000.0,
            positions={"AAPL": {"quantity": 50, "price": 145.0}},
            current_prices={"AAPL": 150.0}
        )
        if result.is_valid:
            # Submit order
        else:
            print(f"Order rejected: {result.error_message}")
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        Initialize order validator.

        Args:
            config: Risk configuration (uses defaults if not provided)
        """
        self.config = config or RiskConfig()

        # Track order timestamps for rate limiting
        self.order_timestamps: deque[tuple[datetime, str]] = deque()

        # Track orders per symbol
        self.symbol_order_timestamps: dict[str, deque[tuple[datetime, str]]] = {}

        logger.info(
            "OrderValidator initialized: max_pos_size=%.0f, max_pos_value=$%.0f, "
            "max_exposure=$%.0f, rate_limit=%d/min",
            self.config.max_position_size,
            self.config.max_position_value,
            self.config.max_total_exposure,
            self.config.max_orders_per_minute,
        )

    def validate(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        cash: float,
        positions: dict[str, dict],
        current_prices: dict[str, float],
    ) -> ValidationResult:
        """
        Validate order against all risk checks.

        Args:
            symbol: Trading symbol
            side: Order side (BUY or SELL)
            quantity: Order quantity
            price: Limit price (None for market orders)
            cash: Available cash
            positions: Current positions as {symbol: {"quantity": float, "price": float}}
            current_prices: Current market prices by symbol

        Returns:
            ValidationResult with is_valid flag and error details
        """
        # 1. Check rate limits
        result = self._check_rate_limits(symbol)
        if not result.is_valid:
            return result

        # 2. Check capital sufficiency
        result = self._check_capital(
            side, quantity, price, cash, current_prices.get(symbol)
        )
        if not result.is_valid:
            return result

        # 3. Check position limits
        result = self._check_position_limits(
            symbol, side, quantity, positions, current_prices
        )
        if not result.is_valid:
            return result

        # 4. Check total exposure
        result = self._check_total_exposure(
            symbol, side, quantity, price, positions, current_prices
        )
        if not result.is_valid:
            return result

        # All checks passed
        return ValidationResult(is_valid=True)

    def validate_order(
        self,
        order_dict: dict,
        cash: float,
        positions: dict[str, dict],
        current_prices: dict[str, float],
    ) -> tuple[bool, str]:
        """
        Validate order dict (convenience method for backward compatibility).

        Args:
            order_dict: Order as dict with 'symbol', 'side', 'quantity', 'price'
            cash: Available cash
            positions: Current positions
            current_prices: Current market prices

        Returns:
            Tuple of (is_valid, error_message)
        """
        result = self.validate(
            symbol=order_dict["symbol"],
            side=order_dict["side"],
            quantity=order_dict["quantity"],
            price=order_dict.get("price"),
            cash=cash,
            positions=positions,
            current_prices=current_prices,
        )
        return result.is_valid, result.error_message

    def record_order(self, symbol: str, order_id: Optional[str] = None) -> None:
        """
        Record order submission for rate limiting.

        Call this AFTER order is successfully submitted.

        Args:
            symbol: Trading symbol
            order_id: Optional order ID for tracking
        """
        now = datetime.now()
        oid = order_id or f"{symbol}-{now.timestamp()}"

        self.order_timestamps.append((now, oid))

        if symbol not in self.symbol_order_timestamps:
            self.symbol_order_timestamps[symbol] = deque()
        self.symbol_order_timestamps[symbol].append((now, oid))

        # Clean old timestamps
        self._clean_old_timestamps()

        logger.debug(
            "Recorded order for %s (total orders: %d)",
            symbol,
            len(self.order_timestamps),
        )

    def _check_rate_limits(self, symbol: str) -> ValidationResult:
        """Check order rate limits."""
        self._clean_old_timestamps()

        # Check global rate limit
        if len(self.order_timestamps) >= self.config.max_orders_per_minute:
            return ValidationResult(
                is_valid=False,
                error_code="RATE_LIMIT_GLOBAL",
                error_message=(
                    f"Global rate limit exceeded: {len(self.order_timestamps)} orders "
                    f"in last minute (limit: {self.config.max_orders_per_minute})"
                ),
                check_failed="rate_limit_global",
            )

        # Check per-symbol rate limit
        symbol_timestamps = self.symbol_order_timestamps.get(symbol, deque())
        if len(symbol_timestamps) >= self.config.max_orders_per_symbol_per_minute:
            return ValidationResult(
                is_valid=False,
                error_code="RATE_LIMIT_SYMBOL",
                error_message=(
                    f"Symbol rate limit exceeded for {symbol}: {len(symbol_timestamps)} orders "
                    f"in last minute (limit: {self.config.max_orders_per_symbol_per_minute})"
                ),
                check_failed="rate_limit_symbol",
            )

        return ValidationResult(is_valid=True)

    def _check_capital(
        self,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        cash: float,
        current_price: Optional[float],
    ) -> ValidationResult:
        """Check if sufficient capital for order."""
        # Only check for buy orders
        if side == OrderSide.SELL:
            return ValidationResult(is_valid=True)

        # Determine order price
        order_price = price if price is not None else current_price
        if order_price is None:
            # Can't validate market order without price - let it through
            return ValidationResult(is_valid=True)

        order_value = quantity * order_price
        available = cash - self.config.min_cash_buffer

        if order_value > available:
            return ValidationResult(
                is_valid=False,
                error_code="INSUFFICIENT_CAPITAL",
                error_message=(
                    f"Order value ${order_value:,.2f} exceeds available cash "
                    f"${available:,.2f} (cash=${cash:,.2f}, buffer=${self.config.min_cash_buffer:,.2f})"
                ),
                check_failed="capital",
            )

        return ValidationResult(is_valid=True)

    def _check_position_limits(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        positions: dict[str, dict],
        current_prices: dict[str, float],
    ) -> ValidationResult:
        """Check position size and value limits."""
        current_position = positions.get(symbol, {})
        current_qty = current_position.get("quantity", 0.0)

        # Calculate new position after order
        if side == OrderSide.BUY:
            new_qty = current_qty + quantity
        else:
            new_qty = current_qty - quantity

        # Check position size limit
        if abs(new_qty) > self.config.max_position_size:
            return ValidationResult(
                is_valid=False,
                error_code="POSITION_SIZE_LIMIT",
                error_message=(
                    f"Position size {abs(new_qty):,.0f} for {symbol} would exceed limit "
                    f"{self.config.max_position_size:,.0f}"
                ),
                check_failed="position_size",
            )

        # Check position value limit
        current_price = current_prices.get(symbol)
        if current_price is not None:
            position_value = abs(new_qty) * current_price
            if position_value > self.config.max_position_value:
                return ValidationResult(
                    is_valid=False,
                    error_code="POSITION_VALUE_LIMIT",
                    error_message=(
                        f"Position value ${position_value:,.2f} for {symbol} would exceed limit "
                        f"${self.config.max_position_value:,.2f}"
                    ),
                    check_failed="position_value",
                )

        return ValidationResult(is_valid=True)

    def _check_total_exposure(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        positions: dict[str, dict],
        current_prices: dict[str, float],
    ) -> ValidationResult:
        """Check total portfolio exposure limit."""
        # Calculate current total exposure
        total_exposure = 0.0
        for sym, pos_info in positions.items():
            pos_qty = pos_info.get("quantity", 0)
            pos_price = current_prices.get(sym) or pos_info.get("price", 0)
            total_exposure += abs(pos_qty) * pos_price

        # Add this order's contribution
        order_price = price if price is not None else current_prices.get(symbol)
        if order_price is not None and side == OrderSide.BUY:
            order_value = quantity * order_price
            total_exposure += order_value
            # Note: For sells, we're reducing exposure, so no need to check

        if total_exposure > self.config.max_total_exposure:
            return ValidationResult(
                is_valid=False,
                error_code="TOTAL_EXPOSURE_LIMIT",
                error_message=(
                    f"Total exposure ${total_exposure:,.2f} would exceed limit "
                    f"${self.config.max_total_exposure:,.2f}"
                ),
                check_failed="total_exposure",
            )

        return ValidationResult(is_valid=True)

    def _clean_old_timestamps(self) -> None:
        """Remove timestamps older than 1 minute."""
        cutoff = datetime.now() - timedelta(minutes=1)

        # Clean global timestamps
        while self.order_timestamps and self.order_timestamps[0][0] < cutoff:
            self.order_timestamps.popleft()

        # Clean per-symbol timestamps
        for symbol in list(self.symbol_order_timestamps.keys()):
            symbol_deque = self.symbol_order_timestamps[symbol]
            while symbol_deque and symbol_deque[0][0] < cutoff:
                symbol_deque.popleft()
            # Remove empty deques
            if not symbol_deque:
                del self.symbol_order_timestamps[symbol]

    def get_rate_stats(self) -> dict:
        """
        Get current order rate statistics.

        Returns:
            Dictionary with rate stats
        """
        self._clean_old_timestamps()
        current = len(self.order_timestamps)
        limit = self.config.max_orders_per_minute

        per_symbol = {
            symbol: len(timestamps)
            for symbol, timestamps in self.symbol_order_timestamps.items()
        }

        return {
            "orders_last_minute": current,
            "global_limit": limit,
            "global_available": max(0, limit - current),
            "per_symbol": per_symbol,
            "symbol_limit": self.config.max_orders_per_symbol_per_minute,
        }

    def reset_rate_tracking(self) -> None:
        """Reset all rate tracking (use with caution, e.g., at start of day)."""
        self.order_timestamps.clear()
        self.symbol_order_timestamps.clear()
        logger.info("Rate tracking reset")

    def __repr__(self) -> str:
        stats = self.get_rate_stats()
        return (
            f"OrderValidator(orders_last_min={stats['orders_last_minute']}, "
            f"limit={stats['global_limit']})"
        )
