"""Tests for risk/risk_manager.py."""

import pytest

from config.trading_config import StopLossConfig
from risk.risk_manager import RiskManager, PositionStop, StopType, ExitSignal
from models import OrderSide, OrderType


class TestPositionStop:
    """Tests for PositionStop dataclass."""

    def test_creation(self):
        """Test creating a position stop."""
        stop = PositionStop(
            symbol="AAPL",
            entry_price=150.0,
            stop_price=147.0,
            highest_price=150.0,
            lowest_price=150.0,
            stop_type=StopType.FIXED_PERCENT,
            quantity=100,
        )
        assert stop.symbol == "AAPL"
        assert stop.entry_price == 150.0
        assert stop.quantity == 100
        assert stop.stop_price == 147.0
        assert stop.stop_type == StopType.FIXED_PERCENT
        assert stop.highest_price == 150.0
        assert stop.lowest_price == 150.0


class TestRiskManager:
    """Tests for RiskManager class."""

    @pytest.fixture
    def config(self):
        """Create a test stop loss config."""
        return StopLossConfig(
            position_stop_pct=2.0,  # 2% stop
            trailing_stop_pct=3.0,  # 3% trailing
            portfolio_stop_pct=5.0,  # 5% portfolio stop
            max_drawdown_pct=10.0,  # 10% max drawdown
            use_trailing_stops=True,
            enable_circuit_breaker=True,
        )

    @pytest.fixture
    def manager(self, config):
        """Create a test risk manager."""
        return RiskManager(config, initial_portfolio_value=100000.0)

    def test_initialization(self, manager):
        """Test risk manager initialization."""
        assert manager.initial_portfolio_value == 100000.0
        assert manager.high_water_mark == 100000.0
        assert manager.circuit_breaker_triggered is False
        assert len(manager.position_stops) == 0

    def test_add_position_stop(self, manager):
        """Test adding a position stop."""
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)

        assert "AAPL" in manager.position_stops
        stop = manager.position_stops["AAPL"]
        assert stop.entry_price == 150.0
        assert stop.quantity == 100
        # 3% trailing stop from entry (config uses trailing stops)
        assert stop.stop_price == pytest.approx(145.5, rel=0.01)

    def test_remove_position_stop(self, manager):
        """Test removing a position stop."""
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)
        assert "AAPL" in manager.position_stops

        manager.remove_position_stop("AAPL")
        assert "AAPL" not in manager.position_stops

    def test_remove_nonexistent_stop(self, manager):
        """Test removing a non-existent stop doesn't raise."""
        manager.remove_position_stop("NONEXISTENT")  # Should not raise

    def test_check_stops_not_triggered(self, manager):
        """Test check_stops when price is above stop."""
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)

        current_prices = {"AAPL": 155.0}  # Above entry
        portfolio_value = 100000.0
        positions = {"AAPL": {"quantity": 100, "price": 150.0}}

        exit_signals = manager.check_stops(current_prices, portfolio_value, positions)
        assert len(exit_signals) == 0

    def test_check_stops_triggered(self, manager):
        """Test check_stops when price hits stop."""
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)

        # Price dropped below 3% trailing stop (145.5)
        current_prices = {"AAPL": 144.0}
        portfolio_value = 100000.0
        positions = {"AAPL": {"quantity": 100, "price": 150.0}}

        exit_signals = manager.check_stops(current_prices, portfolio_value, positions)
        assert len(exit_signals) == 1
        assert exit_signals[0].symbol == "AAPL"
        assert exit_signals[0].side == OrderSide.SELL
        assert exit_signals[0].quantity == 100

    def test_trailing_stop_update(self, manager):
        """Test trailing stop moves up with price."""
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)

        # Price moves up to 160
        current_prices = {"AAPL": 160.0}
        portfolio_value = 100000.0
        positions = {"AAPL": {"quantity": 100, "price": 150.0}}

        # First check - should update highest price and trailing stop
        exit_signals = manager.check_stops(current_prices, portfolio_value, positions)
        assert len(exit_signals) == 0

        stop = manager.position_stops["AAPL"]
        assert stop.highest_price == 160.0
        # Trailing stop should be 3% below 160 = 155.2
        assert stop.stop_price == pytest.approx(155.2, rel=0.01)

    def test_circuit_breaker_daily_loss(self, manager):
        """Test circuit breaker triggers on daily loss."""
        # Set daily start value
        manager.daily_start_value = 100000.0

        # Check with portfolio down 6% (> 5% portfolio stop)
        current_prices = {}
        portfolio_value = 94000.0
        positions = {}

        manager.check_stops(current_prices, portfolio_value, positions)
        assert manager.circuit_breaker_triggered is True

    def test_circuit_breaker_max_drawdown(self, manager):
        """Test circuit breaker triggers on max drawdown."""
        # Peak was 100000
        manager.high_water_mark = 100000.0

        # Portfolio dropped to 89000 (11% drawdown > 10% max)
        current_prices = {}
        portfolio_value = 89000.0
        positions = {}

        manager.check_stops(current_prices, portfolio_value, positions)
        assert manager.circuit_breaker_triggered is True

    def test_reset_daily_tracking(self, manager):
        """Test resetting daily tracking values."""
        manager.daily_start_value = 90000.0

        manager.reset_daily_tracking(current_portfolio_value=100000.0)

        assert manager.daily_start_value == 100000.0

    def test_reset_circuit_breaker(self, manager):
        """Test resetting circuit breaker."""
        manager.circuit_breaker_triggered = True

        manager.reset_circuit_breaker()

        assert manager.circuit_breaker_triggered is False

    def test_get_status(self, manager):
        """Test get_status returns correct info."""
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)

        status = manager.get_status()

        # Check that we have active stops
        assert "active_stops" in status
        assert len(status["active_stops"]) == 1
        assert "AAPL" in status["active_stops"]
        assert "circuit_breaker_triggered" in status
        assert status["circuit_breaker_triggered"] is False
        assert "high_water_mark" in status
        assert status["high_water_mark"] == 100000.0

    def test_disabled_circuit_breaker(self):
        """Test that circuit breaker can be disabled."""
        config = StopLossConfig(enable_circuit_breaker=False)
        manager = RiskManager(config, initial_portfolio_value=100000.0)

        # Large drawdown should not trigger circuit breaker
        manager.high_water_mark = 100000.0
        current_prices = {}
        portfolio_value = 80000.0  # 20% drawdown
        positions = {}

        manager.check_stops(current_prices, portfolio_value, positions)
        assert manager.circuit_breaker_triggered is False

    def test_disabled_trailing_stops(self):
        """Test with trailing stops disabled (fixed stops)."""
        config = StopLossConfig(
            position_stop_pct=2.0,
            use_trailing_stops=False,
        )
        manager = RiskManager(config, initial_portfolio_value=100000.0)
        manager.add_position_stop("AAPL", entry_price=150.0, quantity=100)

        # Price moves up
        current_prices = {"AAPL": 160.0}
        portfolio_value = 100000.0
        positions = {"AAPL": {"quantity": 100, "price": 150.0}}

        manager.check_stops(current_prices, portfolio_value, positions)

        # Stop should remain at original level (2% below entry = 147)
        stop = manager.position_stops["AAPL"]
        assert stop.stop_price == pytest.approx(147.0, rel=0.01)
        # Note: highest_price may or may not update depending on implementation


class TestExitSignal:
    """Tests for ExitSignal dataclass."""

    def test_creation(self):
        """Test creating an exit signal."""
        signal = ExitSignal(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
            reason="Stop loss hit",
            trigger_price=146.0,
            stop_price=147.0,
        )
        assert signal.symbol == "AAPL"
        assert signal.side == OrderSide.SELL
        assert signal.quantity == 100
        assert signal.order_type == OrderType.MARKET
        assert signal.trigger_price == 146.0
        assert signal.stop_price == 147.0
        assert signal.reason == "Stop loss hit"
