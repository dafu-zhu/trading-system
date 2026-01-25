"""Tests for orders/order_validator.py."""

import pytest

from config.trading_config import RiskConfig
from orders.order_validator import OrderValidator, ValidationResult
from models import OrderSide


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.error_message == ""
        assert result.error_code == ""

    def test_invalid_result(self):
        """Test creating an invalid result."""
        result = ValidationResult(
            is_valid=False,
            error_code="INSUFFICIENT_CAPITAL",
            error_message="Insufficient funds",
            check_failed="capital",
        )
        assert result.is_valid is False
        assert result.error_message == "Insufficient funds"
        assert result.error_code == "INSUFFICIENT_CAPITAL"


class TestOrderValidator:
    """Tests for OrderValidator class."""

    @pytest.fixture
    def config(self):
        """Create a test risk config."""
        return RiskConfig(
            max_position_size=1000,
            max_position_value=50000.0,
            max_total_exposure=100000.0,
            max_orders_per_minute=5,
            max_orders_per_symbol_per_minute=2,
            min_cash_buffer=1000.0,
        )

    @pytest.fixture
    def validator(self, config):
        """Create a test order validator."""
        return OrderValidator(config)

    def test_valid_buy_order(self, validator):
        """Test validating a valid buy order."""
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0,
            cash=50000.0,
            positions={},
            current_prices={"AAPL": 150.0},
        )
        assert result.is_valid is True

    def test_valid_sell_order(self, validator):
        """Test validating a valid sell order."""
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50,
            price=155.0,
            cash=10000.0,
            positions={"AAPL": {"quantity": 100, "price": 150.0}},
            current_prices={"AAPL": 155.0},
        )
        assert result.is_valid is True

    def test_insufficient_cash(self, validator):
        """Test rejection for insufficient cash."""
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=500,
            price=150.0,
            cash=5000.0,  # Not enough for 500 * 150 = 75000
            positions={},
            current_prices={"AAPL": 150.0},
        )
        assert result.is_valid is False
        assert (
            "capital" in result.error_code.lower()
            or "capital" in result.check_failed.lower()
        )

    def test_cash_buffer_respected(self, validator):
        """Test that cash buffer is maintained."""
        # Order value = 100 * 150 = 15000
        # Need 15000 + 1000 buffer = 16000
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0,
            cash=15500.0,  # Less than 16000 needed
            positions={},
            current_prices={"AAPL": 150.0},
        )
        assert result.is_valid is False
        assert "capital" in result.check_failed.lower()

    def test_position_size_limit(self, validator):
        """Test rejection for exceeding position size limit."""
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1500,  # Exceeds max_position_size of 1000
            price=30.0,
            cash=100000.0,
            positions={},
            current_prices={"AAPL": 30.0},
        )
        assert result.is_valid is False
        assert (
            "size" in result.check_failed.lower() or "size" in result.error_code.lower()
        )

    def test_position_value_limit(self, validator):
        """Test rejection for exceeding position value limit."""
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=500,
            price=150.0,  # 500 * 150 = 75000 > max_position_value of 50000
            cash=100000.0,
            positions={},
            current_prices={"AAPL": 150.0},
        )
        assert result.is_valid is False
        assert (
            "value" in result.check_failed.lower()
            or "value" in result.error_code.lower()
        )

    def test_total_exposure_limit(self, validator):
        """Test rejection for exceeding total exposure limit."""
        # Existing positions
        positions = {
            "MSFT": {"quantity": 200, "price": 300.0},  # 60000
            "GOOGL": {"quantity": 50, "price": 500.0},  # 25000
        }
        current_prices = {
            "MSFT": 300.0,
            "GOOGL": 500.0,
            "AAPL": 150.0,
        }

        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=200,  # 200 * 150 = 30000 -> total 115000 > 100000
            price=150.0,
            cash=100000.0,
            positions=positions,
            current_prices=current_prices,
        )
        assert result.is_valid is False
        assert (
            "exposure" in result.check_failed.lower()
            or "exposure" in result.error_code.lower()
        )

    def test_rate_limiting(self, validator):
        """Test global rate limiting enforced."""
        # Use different symbols to avoid per-symbol limit (which is 2)
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        # Submit 5 orders (max per minute) across different symbols
        for i, sym in enumerate(symbols):
            result = validator.validate(
                symbol=sym,
                side=OrderSide.BUY,
                quantity=10,
                price=150.0,
                cash=100000.0,
                positions={},
                current_prices={sym: 150.0},
            )
            assert result.is_valid is True, f"Order {i} for {sym} should be valid"
            validator.record_order(sym, f"order_{i}")

        # 6th order should be rejected due to global limit
        result = validator.validate(
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10,
            price=150.0,
            cash=100000.0,
            positions={},
            current_prices={"NVDA": 150.0},
        )
        assert result.is_valid is False
        assert (
            "rate" in result.check_failed.lower() or "rate" in result.error_code.lower()
        )

    def test_rate_limiting_per_symbol(self, validator):
        """Test per-symbol rate limiting."""
        # Submit 2 orders for AAPL (max per symbol)
        for i in range(2):
            result = validator.validate(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=10,
                price=150.0,
                cash=100000.0,
                positions={},
                current_prices={"AAPL": 150.0},
            )
            assert result.is_valid is True
            validator.record_order("AAPL", f"aapl_order_{i}")

        # 3rd order for AAPL should be rejected
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            price=150.0,
            cash=100000.0,
            positions={},
            current_prices={"AAPL": 150.0},
        )
        assert result.is_valid is False

        # But MSFT should still work
        result = validator.validate(
            symbol="MSFT",
            side=OrderSide.BUY,
            quantity=10,
            price=300.0,
            cash=100000.0,
            positions={},
            current_prices={"MSFT": 300.0},
        )
        assert result.is_valid is True

    def test_record_order(self, validator):
        """Test recording orders for rate limiting."""
        validator.record_order("AAPL", "order_1")

        stats = validator.get_rate_stats()
        assert stats["orders_last_minute"] == 1
        assert "AAPL" in stats["per_symbol"]
        assert stats["per_symbol"]["AAPL"] == 1

    def test_get_rate_stats(self, validator):
        """Test getting rate statistics."""
        validator.record_order("AAPL", "order_1")
        validator.record_order("AAPL", "order_2")
        validator.record_order("MSFT", "order_3")

        stats = validator.get_rate_stats()
        assert stats["orders_last_minute"] == 3
        assert stats["per_symbol"]["AAPL"] == 2
        assert stats["per_symbol"]["MSFT"] == 1

    def test_sell_more_than_owned(self, validator):
        """Test that selling more than owned is allowed (short selling)."""
        # The validator allows short selling - it just checks position limits
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=200,  # Only have 100, but short selling allowed
            price=155.0,
            cash=10000.0,
            positions={"AAPL": {"quantity": 100, "price": 150.0}},
            current_prices={"AAPL": 155.0},
        )
        # May be valid or invalid depending on position limits, but not due to ownership
        # The validator just checks if resulting position (-100) is within size limit
        assert result.is_valid is True  # -100 is within 1000 limit

    def test_sell_creates_large_short(self, validator):
        """Test rejection for sell that would exceed position size limit."""
        result = validator.validate(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=1500,  # Would create -1500 position
            price=155.0,
            cash=10000.0,
            positions={},
            current_prices={"AAPL": 155.0},
        )
        assert result.is_valid is False
        assert "size" in result.check_failed.lower()
