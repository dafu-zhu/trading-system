"""Tests for backtester/position_sizer.py."""

import pytest

from backtester.position_sizer import (
    FixedSizer,
    PercentSizer,
    RiskBasedSizer,
    KellySizer,
    VolatilitySizer,
)


class MockPortfolio:
    """Mock portfolio for testing."""

    def __init__(self, total_value: float = 100000.0):
        self._total_value = total_value

    def get_total_value(self) -> float:
        return self._total_value


class TestFixedSizer:
    """Tests for FixedSizer."""

    def test_fixed_quantity(self):
        """Test fixed quantity sizing."""
        sizer = FixedSizer(fixed_qty=100)
        portfolio = MockPortfolio()
        signal = {"action": "BUY", "symbol": "AAPL"}

        qty = sizer.calculate_qty(signal, portfolio, price=150.0)
        assert qty == 100

    def test_min_quantity(self):
        """Test minimum quantity constraint."""
        sizer = FixedSizer(fixed_qty=5, min_qty=10)
        portfolio = MockPortfolio()
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=150.0)
        assert qty == 10

    def test_max_quantity(self):
        """Test maximum quantity constraint."""
        sizer = FixedSizer(fixed_qty=500, max_qty=100)
        portfolio = MockPortfolio()
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=150.0)
        assert qty == 100


class TestPercentSizer:
    """Tests for PercentSizer."""

    def test_percent_of_equity(self):
        """Test percentage of equity sizing."""
        sizer = PercentSizer(equity_percent=0.10)  # 10%
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # 10% of 100000 = 10000 / 100 = 100 shares
        assert qty == pytest.approx(100.0, rel=0.01)

    def test_different_equity_percent(self):
        """Test with different equity percentage."""
        sizer = PercentSizer(equity_percent=0.05)  # 5%
        portfolio = MockPortfolio(total_value=50000.0)
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=50.0)
        # 5% of 50000 = 2500 / 50 = 50 shares
        assert qty == pytest.approx(50.0, rel=0.01)


class TestRiskBasedSizer:
    """Tests for RiskBasedSizer."""

    def test_risk_based_with_stop_loss(self):
        """Test risk-based sizing with stop loss in signal."""
        sizer = RiskBasedSizer(risk_per_trade=0.02)  # 2% risk
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {"stop_loss": 147.0}  # $3 stop distance

        qty = sizer.calculate_qty(signal, portfolio, price=150.0)
        # Risk amount = 100000 * 0.02 = 2000
        # Stop distance = 150 - 147 = 3
        # Qty = 2000 / 3 = 666.67
        assert qty == pytest.approx(666.67, rel=0.01)

    def test_risk_based_with_stop_loss_pct(self):
        """Test risk-based sizing with stop loss percentage."""
        sizer = RiskBasedSizer(risk_per_trade=0.02)
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {"stop_loss_pct": 0.02}  # 2% stop

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Risk amount = 100000 * 0.02 = 2000
        # Stop distance = 100 * 0.02 = 2
        # Qty = 2000 / 2 = 1000
        assert qty == pytest.approx(1000.0, rel=0.01)

    def test_risk_based_default_stop(self):
        """Test risk-based sizing with default stop loss."""
        sizer = RiskBasedSizer(risk_per_trade=0.01)  # 1% risk
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {}  # No stop loss, uses default 2%

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Risk amount = 100000 * 0.01 = 1000
        # Stop distance = 100 * 0.02 = 2 (default)
        # Qty = 1000 / 2 = 500
        assert qty == pytest.approx(500.0, rel=0.01)


class TestKellySizer:
    """Tests for KellySizer."""

    def test_kelly_calculation(self):
        """Test Kelly criterion calculation."""
        sizer = KellySizer()

        # f* = (p*b - q) / b where p=0.55, b=1.5, q=0.45
        # f* = (0.55 * 1.5 - 0.45) / 1.5 = (0.825 - 0.45) / 1.5 = 0.25
        kelly = sizer.calculate_kelly_fraction(win_rate=0.55, win_loss_ratio=1.5)
        assert kelly == pytest.approx(0.25, rel=0.01)

    def test_kelly_no_edge(self):
        """Test Kelly returns negative when no edge."""
        sizer = KellySizer()

        # p=0.40, b=1.0, q=0.60
        # f* = (0.40 * 1.0 - 0.60) / 1.0 = -0.20
        kelly = sizer.calculate_kelly_fraction(win_rate=0.40, win_loss_ratio=1.0)
        assert kelly == pytest.approx(-0.20, rel=0.01)

    def test_kelly_sizing(self):
        """Test Kelly criterion position sizing."""
        sizer = KellySizer(
            win_rate=0.55,
            win_loss_ratio=1.5,
            kelly_fraction=0.5,  # Half Kelly
            max_position_pct=0.25,
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Kelly = 0.25, Half Kelly = 0.125
        # Position value = 100000 * 0.125 = 12500
        # Qty = 12500 / 100 = 125
        assert qty == pytest.approx(125.0, rel=0.01)

    def test_kelly_no_edge_returns_zero(self):
        """Test Kelly sizer returns 0 when no edge."""
        sizer = KellySizer(
            win_rate=0.40,  # No edge
            win_loss_ratio=1.0,
            kelly_fraction=0.5,
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        assert qty == 0.0

    def test_kelly_max_position_cap(self):
        """Test Kelly respects max position cap."""
        sizer = KellySizer(
            win_rate=0.70,  # Strong edge
            win_loss_ratio=2.0,
            kelly_fraction=1.0,  # Full Kelly
            max_position_pct=0.10,  # But capped at 10%
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {}

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Should be capped at 10% = 10000 / 100 = 100 shares
        assert qty == pytest.approx(100.0, rel=0.01)

    def test_kelly_signal_override(self):
        """Test signal can override win_rate and win_loss_ratio."""
        sizer = KellySizer(
            win_rate=0.50,
            win_loss_ratio=1.0,
            kelly_fraction=1.0,
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {
            "win_rate": 0.60,
            "win_loss_ratio": 2.0,
        }

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Using signal values: kelly = (0.60 * 2.0 - 0.40) / 2.0 = 0.40
        # Position value = 100000 * 0.40 = 40000 / 100 = 400 (but capped at 25%)
        assert qty > 0


class TestVolatilitySizer:
    """Tests for VolatilitySizer."""

    def test_volatility_sizing_with_atr(self):
        """Test volatility sizing with ATR in signal."""
        sizer = VolatilitySizer(
            risk_pct=0.02,  # 2% risk
            atr_multiplier=2.0,  # Stop at 2x ATR
            max_position_pct=0.50,  # High max to not interfere
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {"atr": 2.50}  # $2.50 ATR

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Risk amount = 100000 * 0.02 = 2000
        # Stop distance = 2.50 * 2 = 5.00
        # Qty = 2000 / 5 = 400
        assert qty == pytest.approx(400.0, rel=0.01)

    def test_volatility_sizing_with_volatility_pct(self):
        """Test volatility sizing with volatility percentage."""
        sizer = VolatilitySizer(
            risk_pct=0.02,
            atr_multiplier=2.0,
            max_position_pct=0.80,  # Higher max to not interfere
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {"volatility": 0.015}  # 1.5% volatility

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # ATR = 100 * 0.015 = 1.50
        # Stop distance = 1.50 * 2 = 3.00
        # Risk amount = 100000 * 0.02 = 2000
        # Qty = 2000 / 3 = 666.67
        assert qty == pytest.approx(666.67, rel=0.01)

    def test_volatility_sizing_default_atr(self):
        """Test volatility sizing with default ATR."""
        sizer = VolatilitySizer(
            risk_pct=0.02,
            atr_multiplier=2.0,
            default_atr_pct=0.02,  # Default 2% ATR
            max_position_pct=0.50,
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {}  # No ATR in signal

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # ATR = 100 * 0.02 = 2.00
        # Stop distance = 2.00 * 2 = 4.00
        # Risk amount = 100000 * 0.02 = 2000
        # Qty = 2000 / 4 = 500
        assert qty == pytest.approx(500.0, rel=0.01)

    def test_volatility_max_position_cap(self):
        """Test volatility sizer respects max position cap."""
        sizer = VolatilitySizer(
            risk_pct=0.10,  # High risk
            atr_multiplier=1.0,  # Tight stop
            max_position_pct=0.10,  # But capped at 10%
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {"atr": 0.50}  # Small ATR

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Max qty = (100000 * 0.10) / 100 = 100
        assert qty <= 100.0

    def test_volatility_min_qty(self):
        """Test volatility sizer respects min qty."""
        sizer = VolatilitySizer(
            risk_pct=0.001,  # Very low risk
            atr_multiplier=2.0,
            min_qty=1.0,
        )
        portfolio = MockPortfolio(total_value=10000.0)
        signal = {"atr": 5.0}

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        assert qty >= 1.0

    def test_volatility_zero_atr_fallback(self):
        """Test volatility sizer handles zero ATR."""
        sizer = VolatilitySizer(
            risk_pct=0.02,
            atr_multiplier=2.0,
            default_atr_pct=0.02,
        )
        portfolio = MockPortfolio(total_value=100000.0)
        signal = {"atr": 0}  # Zero ATR

        qty = sizer.calculate_qty(signal, portfolio, price=100.0)
        # Should use default ATR
        assert qty > 0
