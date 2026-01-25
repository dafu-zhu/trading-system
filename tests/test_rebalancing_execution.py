"""
Tests for rebalancing execution module.

Tests RebalancingPlan, TWAPExecutor, RateLimitedQueue, ExecutionMonitor, AggressiveHandler.
"""

import pytest
from datetime import date, time, datetime
from unittest.mock import MagicMock

from models import OrderSide
from execution.rebalancing_plan import PlannedTrade, RebalancingPlan, RebalancingPlanner
from execution.twap_executor import TWAPExecutor, OrderSlice, ExecutionReport
from execution.rate_limited_queue import RateLimitedOrderQueue, QueuedOrder
from execution.execution_monitor import ExecutionMonitor
from execution.aggressive_handler import AggressiveCompletionHandler


class TestRebalancingPlan:
    """Tests for RebalancingPlan and RebalancingPlanner."""

    @pytest.fixture
    def planner(self):
        """Create a planner instance."""
        return RebalancingPlanner(
            start_time=time(9, 30),
            aggressive_time=time(15, 30),
        )

    def test_create_plan_from_positions(self, planner):
        """Test that plan correctly computes trades from position diff."""
        current = {"AAPL": 100, "MSFT": 50}
        target = {"AAPL": 150, "MSFT": 0, "GOOGL": 75}

        plan = planner.create_plan(current, target)

        assert plan.total_trades == 3

        # Check individual trades
        trades_by_symbol = {t.symbol: t for t in plan.trades}

        # AAPL: 100 -> 150 = BUY 50
        assert trades_by_symbol["AAPL"].side == OrderSide.BUY
        assert trades_by_symbol["AAPL"].quantity == 50

        # MSFT: 50 -> 0 = SELL 50
        assert trades_by_symbol["MSFT"].side == OrderSide.SELL
        assert trades_by_symbol["MSFT"].quantity == 50

        # GOOGL: 0 -> 75 = BUY 75
        assert trades_by_symbol["GOOGL"].side == OrderSide.BUY
        assert trades_by_symbol["GOOGL"].quantity == 75

    def test_priority_by_trade_size(self, planner):
        """Test that larger trades get higher priority."""
        current = {"AAPL": 0, "MSFT": 0, "GOOGL": 0}
        target = {"AAPL": 100, "MSFT": 500, "GOOGL": 200}
        prices = {"AAPL": 180.0, "MSFT": 380.0, "GOOGL": 140.0}

        plan = planner.create_plan(current, target, current_prices=prices)

        # Get trades sorted by priority
        sorted_trades = plan.get_trades_by_priority()

        # MSFT has highest notional value (500 * 380 = 190,000)
        # Should have highest priority
        assert sorted_trades[0].symbol == "MSFT"

    def test_plan_with_empty_target(self, planner):
        """Test handling empty target positions."""
        current = {"AAPL": 100, "MSFT": 50}
        target = {}

        plan = planner.create_plan(current, target)

        # Should sell all current positions
        assert plan.total_trades == 2
        assert plan.total_sells == 2
        assert plan.total_buys == 0

    def test_plan_no_changes_needed(self, planner):
        """Test when positions are already at target."""
        current = {"AAPL": 100, "MSFT": 50}
        target = {"AAPL": 100, "MSFT": 50}

        plan = planner.create_plan(current, target)

        assert plan.total_trades == 0

    def test_planned_trade_properties(self):
        """Test PlannedTrade dataclass."""
        trade = PlannedTrade(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            priority=5,
            limit_price=180.0,
        )

        assert trade.notional_value == 18000.0


class TestTWAPExecutor:
    """Tests for TWAP execution algorithm."""

    @pytest.fixture
    def executor(self):
        """Create executor in dry run mode."""
        return TWAPExecutor(
            trading_gateway=None,
            rate_limit=200,
            num_slices=10,
            dry_run=True,
        )

    @pytest.fixture
    def sample_plan(self):
        """Create a sample rebalancing plan."""
        trades = [
            PlannedTrade("AAPL", OrderSide.BUY, 100, priority=2, limit_price=180.0),
            PlannedTrade("MSFT", OrderSide.BUY, 50, priority=1, limit_price=380.0),
        ]
        return RebalancingPlan(
            target_date=date.today(),
            trades=trades,
            start_time=time(9, 30),
            aggressive_time=time(15, 30),
        )

    def test_split_into_equal_slices(self, executor):
        """Test that order is split evenly across time slices."""
        trade = PlannedTrade("AAPL", OrderSide.BUY, 100, priority=1)

        slices = executor._split_into_slices(trade, 10)

        assert len(slices) == 10
        total_qty = sum(s.quantity for s in slices)
        assert total_qty == 100

        # Each slice should be ~10 shares
        for s in slices:
            assert s.quantity == 10

    def test_split_with_remainder(self, executor):
        """Test splitting with uneven division."""
        trade = PlannedTrade("AAPL", OrderSide.BUY, 105, priority=1)

        slices = executor._split_into_slices(trade, 10)

        total_qty = sum(s.quantity for s in slices)
        assert total_qty == 105

        # First 5 slices get 11 shares, rest get 10
        assert slices[0].quantity == 11
        assert slices[5].quantity == 10

    def test_schedule_slices_across_timeframe(self, executor):
        """Test that slices are distributed from start to end time."""
        slices = [OrderSlice("AAPL", OrderSide.BUY, 10, time(9, 30)) for _ in range(10)]

        scheduled = executor._schedule_slices(slices, time(9, 30), time(15, 30))

        # First slice at start time
        assert scheduled[0].scheduled_time == time(9, 30)

        # Slices should be spread across the window
        times = [s.scheduled_time for s in scheduled]
        # Should have increasing times
        for i in range(1, len(times)):
            assert times[i] >= times[i - 1]

    def test_execute_plan_dry_run(self, executor, sample_plan):
        """Test dry run execution."""
        report = executor.execute_plan(sample_plan)

        assert isinstance(report, ExecutionReport)
        assert report.total_trades == 2
        assert report.completed_trades == 2
        assert report.failed_trades == 0

    def test_execute_plan_respects_rate_limit(self, executor, sample_plan):
        """Test that execution respects rate limit."""
        executor.rate_limit = 200

        report = executor.execute_plan(sample_plan)

        # All trades should complete (small plan)
        assert report.completed_trades == sample_plan.total_trades


class TestRateLimitedQueue:
    """Tests for rate-limited order queue."""

    @pytest.fixture
    def queue(self):
        """Create a queue instance."""
        return RateLimitedOrderQueue(max_per_minute=200)

    def test_enqueue_with_priority(self, queue):
        """Test that orders are enqueued with correct priority."""
        order1 = QueuedOrder("AAPL", OrderSide.BUY, 100, priority=1)
        order2 = QueuedOrder("MSFT", OrderSide.BUY, 50, priority=10)

        queue.enqueue(order1)
        queue.enqueue(order2)

        assert queue.get_pending_count() == 2

    def test_process_batch_respects_limit(self, queue):
        """Test that batch processing stays within limit."""
        # Add 250 orders (more than 200 limit)
        for i in range(250):
            order = QueuedOrder(f"SYM{i}", OrderSide.BUY, 10, priority=i)
            queue.enqueue(order)

        # Process batch
        results = queue.process_batch()

        # Should process at most 200
        assert len(results) <= 200
        assert queue.get_pending_count() == 250 - len(results)

    def test_priority_ordering(self, queue):
        """Test that higher priority orders are processed first."""
        order_low = QueuedOrder("LOW", OrderSide.BUY, 10, priority=1)
        order_high = QueuedOrder("HIGH", OrderSide.BUY, 10, priority=100)
        order_med = QueuedOrder("MED", OrderSide.BUY, 10, priority=50)

        queue.enqueue(order_low)
        queue.enqueue(order_high)
        queue.enqueue(order_med)

        results = queue.process_batch(batch_size=3)

        # Should be processed in priority order
        symbols = [r.order.symbol for r in results]
        assert symbols == ["HIGH", "MED", "LOW"]

    def test_get_available_capacity(self, queue):
        """Test capacity calculation."""
        assert queue.get_available_capacity() == 200

        # Process some orders
        for i in range(50):
            order = QueuedOrder(f"SYM{i}", OrderSide.BUY, 10, priority=i)
            queue.enqueue(order)

        queue.process_batch(batch_size=50)

        # Capacity should be reduced
        assert queue.get_available_capacity() == 150


class TestExecutionMonitor:
    """Tests for execution quality monitoring."""

    @pytest.fixture
    def monitor(self):
        """Create a monitor instance."""
        return ExecutionMonitor()

    def test_track_fill(self, monitor):
        """Test fill tracking records correctly."""
        monitor.track_fill(
            symbol="AAPL",
            side="buy",
            quantity=100,
            fill_price=180.50,
            fill_time=datetime.now(),
        )

        assert len(monitor._fills) == 1
        assert "AAPL" in monitor._fills_by_symbol

    def test_execution_vwap_calculation(self, monitor):
        """Test execution VWAP is calculated correctly."""
        # Two fills at different prices
        monitor.track_fill("AAPL", "buy", 100, 180.00, datetime.now())
        monitor.track_fill("AAPL", "buy", 100, 182.00, datetime.now())

        vwap = monitor.get_execution_vwap("AAPL")

        # VWAP should be (100*180 + 100*182) / 200 = 181
        assert vwap == pytest.approx(181.0)

    def test_vwap_comparison_calculation(self, monitor):
        """Test VWAP comparison returns correct basis points."""
        monitor.track_fill("AAPL", "buy", 100, 181.00, datetime.now())
        monitor.set_market_vwap("AAPL", 180.00)

        comparison = monitor.get_vwap_comparison("AAPL")

        # Executed at 181 vs market 180 = 0.56% worse = ~56 bps
        expected_bps = (181 - 180) / 180 * 10000
        assert comparison == pytest.approx(expected_bps, rel=0.01)

    def test_slippage_report(self, monitor):
        """Test slippage is calculated correctly per symbol."""
        monitor.track_fill(
            "AAPL", "buy", 100, 181.00, datetime.now(),
            expected_price=180.00
        )
        monitor.track_fill(
            "MSFT", "buy", 50, 382.00, datetime.now(),
            expected_price=380.00
        )

        report = monitor.get_slippage_report()

        assert "AAPL" in report
        assert "MSFT" in report
        # AAPL: (181-180)/180 * 10000 = 55.56 bps
        assert report["AAPL"] == pytest.approx(55.56, rel=0.1)

    def test_completion_status(self, monitor):
        """Test completion status tracking."""
        monitor.set_planned_trades([
            {"symbol": "AAPL", "quantity": 100, "side": "buy"},
            {"symbol": "MSFT", "quantity": 50, "side": "buy"},
        ])

        # Complete one trade
        monitor.track_fill("AAPL", "buy", 100, 180.00, datetime.now())

        status = monitor.get_completion_status()

        assert status.total_planned == 2
        assert status.completed == 1
        assert status.pending == 1
        assert status.completion_pct == 50.0


class TestAggressiveHandler:
    """Tests for aggressive completion handler."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return AggressiveCompletionHandler(cutoff_time=time(15, 30))

    def test_escalate_at_cutoff_time(self, handler):
        """Test that pending orders are converted at cutoff time."""
        pending = [
            PlannedTrade("AAPL", OrderSide.BUY, 100, priority=1, limit_price=180.0),
            PlannedTrade("MSFT", OrderSide.BUY, 50, priority=2, limit_price=380.0),
        ]

        # Before cutoff
        before_cutoff = datetime(2024, 1, 15, 14, 0)
        orders = handler.check_and_escalate(pending, before_cutoff)
        assert len(orders) == 0

        # At cutoff
        at_cutoff = datetime(2024, 1, 15, 15, 30)
        orders = handler.check_and_escalate(pending, at_cutoff)
        assert len(orders) == 2

    def test_convert_to_market_orders(self, handler):
        """Test that limit orders are converted to market orders."""
        pending = [
            PlannedTrade("AAPL", OrderSide.BUY, 100, priority=1, limit_price=180.0),
        ]

        at_cutoff = datetime(2024, 1, 15, 15, 30)
        orders = handler.check_and_escalate(pending, at_cutoff)

        assert len(orders) == 1
        assert orders[0].original_limit_price == 180.0
        assert orders[0].reason == "cutoff_time_reached"

    def test_should_use_market_order(self, handler):
        """Test market order decision logic."""
        trade = PlannedTrade("AAPL", OrderSide.BUY, 100, limit_price=180.0)

        # Before cutoff - use limit
        before = datetime(2024, 1, 15, 10, 0)
        assert not handler.should_use_market_order(trade, before)

        # After cutoff - use market
        after = datetime(2024, 1, 15, 16, 0)
        assert handler.should_use_market_order(trade, after)

    def test_no_duplicate_escalation(self, handler):
        """Test that symbols are only escalated once."""
        pending = [
            PlannedTrade("AAPL", OrderSide.BUY, 100, priority=1),
        ]

        at_cutoff = datetime(2024, 1, 15, 15, 30)

        # First escalation
        orders1 = handler.check_and_escalate(pending, at_cutoff)
        assert len(orders1) == 1

        # Second call - should not re-escalate
        orders2 = handler.check_and_escalate(pending, at_cutoff)
        assert len(orders2) == 0

    def test_reset(self, handler):
        """Test handler reset for new day."""
        pending = [PlannedTrade("AAPL", OrderSide.BUY, 100, priority=1)]
        at_cutoff = datetime(2024, 1, 15, 15, 30)

        handler.check_and_escalate(pending, at_cutoff)
        assert "AAPL" in handler.get_escalated_symbols()

        handler.reset()
        assert len(handler.get_escalated_symbols()) == 0


@pytest.mark.integration
class TestRebalancingIntegration:
    """Integration tests for full rebalancing flow."""

    def test_end_to_end_with_mock_gateway(self):
        """Test full rebalancing flow with mocked TradingGateway."""
        # Create mock gateway
        mock_gateway = MagicMock()
        mock_gateway.submit_order.return_value = MagicMock(
            order_id="123",
            status="filled",
            filled_quantity=100,
            filled_avg_price=180.0,
        )

        # Create plan
        planner = RebalancingPlanner()
        current = {"AAPL": 0}
        target = {"AAPL": 100}
        plan = planner.create_plan(current, target)

        # Execute (in dry run mode to avoid actual gateway calls)
        executor = TWAPExecutor(
            trading_gateway=mock_gateway,
            dry_run=True,  # Use dry run for test
        )
        report = executor.execute_plan(plan)

        assert report.total_trades == 1
        assert report.completed_trades == 1
