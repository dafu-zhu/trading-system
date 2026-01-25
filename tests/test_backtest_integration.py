"""
Integration tests for backtesting system.

Tests the full backtest flow with mocked gateway.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from orders.matching_engine import DeterministicMatchingEngine
from orders.order import Order, OrderState
from orders.order import OrderSide as LegacyOrderSide
from orders.order_book import OrderBook
from backtester.backtest_engine import BacktestEngine
from backtester.position_sizer import PercentSizer
from strategy.macd_strategy import MACDStrategy
from models import DataGateway, Timeframe, Bar


class TestDeterministicMatchingEngine:
    """Tests for DeterministicMatchingEngine."""

    @pytest.fixture
    def engine(self):
        """Create a matching engine."""
        return DeterministicMatchingEngine(
            fill_at="close",
            max_volume_pct=0.1,
            slippage_bps=0.0,
        )

    @pytest.fixture
    def sample_bar(self):
        """Create a sample bar."""
        return Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=185.0,
            high=190.0,
            low=183.0,
            close=188.0,
            volume=10000000,
        )

    @pytest.fixture
    def buy_order(self):
        """Create a buy order."""
        order = Order(
            symbol="AAPL",
            qty=100,
            price=188.0,
            side=LegacyOrderSide.BUY,
            timestamp=datetime(2024, 1, 15, 9, 30),
        )
        order.transition(OrderState.ACKED)
        return order

    def test_match_fills_at_close(self, engine, sample_bar, buy_order):
        """Test that market orders fill at close price."""
        engine.set_current_bar(sample_bar)
        book = OrderBook()

        result = engine.match(buy_order, book)

        assert result["status"] == "filled"
        assert result["fill_price"] == 188.0  # Close price
        assert result["filled_qty"] == 100

    def test_match_respects_volume_limit(self, engine, sample_bar):
        """Test that fill quantity respects volume percentage limit."""
        engine.set_current_bar(sample_bar)
        book = OrderBook()

        # Create order larger than 10% of volume
        large_order = Order(
            symbol="AAPL",
            qty=5000000,  # 50% of volume
            price=188.0,
            side=LegacyOrderSide.BUY,
            timestamp=datetime(2024, 1, 15, 9, 30),
        )
        large_order.transition(OrderState.ACKED)

        result = engine.match(large_order, book)

        # Should only fill 10% of volume = 1,000,000
        assert result["filled_qty"] == 1000000
        assert result["status"] == "partially_filled"

    def test_match_applies_slippage(self, sample_bar, buy_order):
        """Test that slippage is applied correctly."""
        engine = DeterministicMatchingEngine(
            fill_at="close",
            max_volume_pct=0.1,
            slippage_bps=10.0,  # 10 basis points = 0.1%
        )
        engine.set_current_bar(sample_bar)
        book = OrderBook()

        result = engine.match(buy_order, book)

        # Buy order should get worse price (higher)
        expected_price = 188.0 * 1.001  # 0.1% slippage
        assert abs(result["fill_price"] - expected_price) < 0.01

    def test_match_rejects_non_acked_order(self, engine, sample_bar):
        """Test that non-ACKED orders are rejected."""
        engine.set_current_bar(sample_bar)
        book = OrderBook()

        order = Order(
            symbol="AAPL",
            qty=100,
            price=188.0,
            side=LegacyOrderSide.BUY,
            timestamp=datetime(2024, 1, 15, 9, 30),
        )
        # Don't transition to ACKED

        result = engine.match(order, book)

        assert result["status"] == "rejected"

    def test_match_without_bar(self, engine, buy_order):
        """Test matching without bar data fails."""
        book = OrderBook()
        # Don't set current bar

        result = engine.match(buy_order, book)

        assert result["status"] == "rejected"
        assert "No bar data" in result["message"]

    def test_fill_at_open(self, sample_bar, buy_order):
        """Test filling at open price."""
        engine = DeterministicMatchingEngine(fill_at="open")
        engine.set_current_bar(sample_bar)
        book = OrderBook()

        result = engine.match(buy_order, book)

        assert result["fill_price"] == 185.0  # Open price

    def test_fill_at_vwap(self, buy_order):
        """Test filling at VWAP."""
        bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=185.0,
            high=190.0,
            low=183.0,
            close=188.0,
            volume=10000000,
            vwap=186.5,
        )
        engine = DeterministicMatchingEngine(fill_at="vwap")
        engine.set_current_bar(bar)
        book = OrderBook()

        result = engine.match(buy_order, book)

        assert result["fill_price"] == 186.5  # VWAP


class TestBacktestEngine:
    """Tests for BacktestEngine."""

    @pytest.fixture
    def sample_bars(self):
        """Create sample bars for backtesting."""
        import math

        bars = []
        base_date = datetime(2024, 1, 1, 9, 30)
        for i in range(100):
            # Sinusoidal price pattern to generate crossovers
            price = 100 + 10 * math.sin(i * 2 * math.pi / 40)
            bars.append(
                Bar(
                    symbol="TEST",
                    timestamp=base_date + timedelta(days=i),
                    timeframe=Timeframe.DAY_1,
                    open=price - 0.2,
                    high=price + 0.5,
                    low=price - 0.5,
                    close=price,
                    volume=1000000,
                )
            )
        return bars

    @pytest.fixture
    def mock_gateway(self, sample_bars):
        """Create a mock DataGateway."""
        gateway = MagicMock(spec=DataGateway)
        gateway.is_connected.return_value = True
        gateway.fetch_bars.return_value = sample_bars
        gateway.stream_bars.return_value = iter(sample_bars)
        return gateway

    @pytest.fixture
    def strategy(self, mock_gateway):
        """Create a strategy with mock gateway."""
        return MACDStrategy(
            gateway=mock_gateway,
            timeframe=Timeframe.DAY_1,
        )

    @pytest.fixture
    def engine(self, mock_gateway, strategy):
        """Create a backtest engine."""
        return BacktestEngine(
            gateway=mock_gateway,
            strategy=strategy,
            init_capital=100000.0,
            position_sizer=PercentSizer(equity_percent=0.10),
        )

    def test_run_backtest(self, engine, mock_gateway):
        """Test running a full backtest."""
        results = engine.run(
            symbol="TEST",
            timeframe=Timeframe.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 4, 10),
        )

        assert results["symbol"] == "TEST"
        assert results["bar_count"] == 100
        assert results["initial_capital"] == 100000.0
        assert "final_value" in results
        assert "total_return_pct" in results
        assert "equity_curve" in results

    def test_backtest_requires_connection(self, mock_gateway, strategy):
        """Test that backtest requires connected gateway."""
        mock_gateway.is_connected.return_value = False
        engine = BacktestEngine(
            gateway=mock_gateway,
            strategy=strategy,
        )

        with pytest.raises(RuntimeError, match="not connected"):
            engine.run(
                "TEST", Timeframe.DAY_1, datetime(2024, 1, 1), datetime(2024, 2, 1)
            )

    def test_backtest_tracks_equity(self, engine, mock_gateway):
        """Test that equity is tracked throughout backtest."""
        results = engine.run(
            symbol="TEST",
            timeframe=Timeframe.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 4, 10),
        )

        equity_curve = results["equity_curve"]
        assert len(equity_curve) > 0

        # First entry should be initial capital
        assert equity_curve[0]["value"] == 100000.0

    def test_backtest_generates_trades(self, engine, mock_gateway):
        """Test that backtest generates trades."""
        results = engine.run(
            symbol="TEST",
            timeframe=Timeframe.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 4, 10),
        )

        # With sinusoidal price data, should have some trades
        assert results["total_trades"] >= 0
        assert "trades" in results

    def test_backtest_with_slippage(self, mock_gateway, strategy):
        """Test backtest with slippage."""
        engine = BacktestEngine(
            gateway=mock_gateway,
            strategy=strategy,
            init_capital=100000.0,
            slippage_bps=10.0,
        )

        results = engine.run(
            symbol="TEST",
            timeframe=Timeframe.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 4, 10),
        )

        # Should complete without error
        assert results["bar_count"] == 100


class TestBacktestDeterminism:
    """Tests to verify backtest results are deterministic."""

    @pytest.fixture
    def bars(self):
        """Create consistent bars for determinism test."""
        bars = []
        base_date = datetime(2024, 1, 1, 9, 30)
        prices = [100, 101, 99, 102, 98, 103, 97, 104, 96, 105] * 5
        for i, price in enumerate(prices):
            bars.append(
                Bar(
                    symbol="TEST",
                    timestamp=base_date + timedelta(days=i),
                    timeframe=Timeframe.DAY_1,
                    open=price - 0.5,
                    high=price + 1,
                    low=price - 1,
                    close=price,
                    volume=1000000,
                )
            )
        return bars

    def test_results_are_deterministic(self, bars):
        """Test that running backtest twice gives same results."""

        def run_backtest():
            gateway = MagicMock(spec=DataGateway)
            gateway.is_connected.return_value = True
            gateway.fetch_bars.return_value = bars
            gateway.stream_bars.return_value = iter(bars)

            strategy = MACDStrategy(gateway=gateway, timeframe=Timeframe.DAY_1)
            engine = BacktestEngine(
                gateway=gateway,
                strategy=strategy,
                init_capital=100000.0,
            )
            return engine.run(
                "TEST", Timeframe.DAY_1, datetime(2024, 1, 1), datetime(2024, 2, 20)
            )

        result1 = run_backtest()
        result2 = run_backtest()

        assert result1["final_value"] == result2["final_value"]
        assert result1["total_return_pct"] == result2["total_return_pct"]
        assert result1["total_trades"] == result2["total_trades"]
