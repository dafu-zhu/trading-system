"""Tests for gateway/order_gateway.py."""

import csv
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from gateway.order_gateway import (
    OrderGateway,
    OrderEvent,
    OrderEventType,
    CSV_HEADERS,
)


class TestOrderEvent:
    """Tests for OrderEvent dataclass."""

    def test_creation(self):
        """Test creating an order event."""
        event = OrderEvent(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            event_type=OrderEventType.SENT,
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
            status="new",
        )
        assert event.order_id == "123"
        assert event.symbol == "AAPL"
        assert event.event_type == OrderEventType.SENT

    def test_to_csv_row(self):
        """Test converting event to CSV row."""
        event = OrderEvent(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            event_type=OrderEventType.FILLED,
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
            status="filled",
            filled_qty=100,
            avg_fill_price=150.25,
            message="Success",
        )

        row = event.to_csv_row()
        assert len(row) == 12
        assert row[1] == "FILLED"
        assert row[2] == "123"
        assert row[3] == "AAPL"
        assert row[9] == 100  # filled_qty
        assert row[10] == 150.25  # avg_fill_price

    def test_from_csv_row(self):
        """Test creating event from CSV row."""
        row = [
            "2024-01-15T10:30:00",
            "SENT",
            "123",
            "AAPL",
            "buy",
            "market",
            "100",
            "150.0",
            "new",
            "0",
            "0",
            "Test message",
        ]

        event = OrderEvent.from_csv_row(row)
        assert event.order_id == "123"
        assert event.symbol == "AAPL"
        assert event.event_type == OrderEventType.SENT
        assert event.message == "Test message"


class TestOrderGateway:
    """Tests for OrderGateway class."""

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file path."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        yield path
        # Cleanup
        Path(path).unlink(missing_ok=True)

    @pytest.fixture
    def gateway(self, temp_log_file):
        """Create a test order gateway."""
        return OrderGateway(log_file=temp_log_file, append=False)

    def test_initialization(self, temp_log_file):
        """Test gateway initialization creates file with headers."""
        OrderGateway(log_file=temp_log_file, append=False)

        assert Path(temp_log_file).exists()

        with open(temp_log_file) as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert headers == CSV_HEADERS

    def test_log_order_sent(self, gateway, temp_log_file):
        """Test logging order sent event."""
        gateway.log_order_sent(
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
        )

        assert len(gateway._events) == 1
        assert gateway._events[0].event_type == OrderEventType.SENT
        assert gateway._events[0].order_id == "123"

        # Check file
        with open(temp_log_file) as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            row = next(reader)
            assert row[1] == "SENT"
            assert row[2] == "123"

    def test_log_order_filled(self, gateway):
        """Test logging order filled event."""
        # First send an order
        gateway.log_order_sent(
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
        )

        # Then log fill
        gateway.log_order_filled(
            order_id="123",
            symbol="AAPL",
            filled_qty=100,
            avg_price=150.25,
        )

        assert len(gateway._events) == 2
        fill_event = gateway._events[1]
        assert fill_event.event_type == OrderEventType.FILLED
        assert fill_event.filled_qty == 100
        assert fill_event.avg_fill_price == 150.25

    def test_log_order_rejected(self, gateway):
        """Test logging order rejected event."""
        gateway.log_order_rejected(
            order_id="456",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
            reason="Insufficient funds",
        )

        assert len(gateway._events) == 1
        assert gateway._events[0].event_type == OrderEventType.REJECTED
        assert gateway._events[0].message == "Insufficient funds"

    def test_log_order_cancelled(self, gateway):
        """Test logging order cancelled event."""
        # First send an order
        gateway.log_order_sent(
            order_id="789",
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=100,
            price=145.0,
        )

        # Then cancel
        gateway.log_order_cancelled(
            order_id="789",
            symbol="AAPL",
            reason="User requested",
        )

        assert len(gateway._events) == 2
        cancel_event = gateway._events[1]
        assert cancel_event.event_type == OrderEventType.CANCELLED
        assert cancel_event.message == "User requested"

    def test_log_partial_fill(self, gateway):
        """Test logging partial fill event."""
        gateway.log_order_sent(
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
        )

        gateway.log_order_filled(
            order_id="123",
            symbol="AAPL",
            filled_qty=50,
            avg_price=150.10,
            partial=True,
        )

        assert gateway._events[1].event_type == OrderEventType.PARTIAL_FILL
        assert gateway._events[1].filled_qty == 50

    def test_get_order_history(self, gateway):
        """Test retrieving order history."""
        gateway.log_order_sent(
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
        )
        gateway.log_order_filled(
            order_id="123",
            symbol="AAPL",
            filled_qty=100,
            avg_price=150.25,
        )

        history = gateway.get_order_history("123")
        assert len(history) == 2
        assert history[0].event_type == OrderEventType.SENT
        assert history[1].event_type == OrderEventType.FILLED

    def test_get_order_history_nonexistent(self, gateway):
        """Test retrieving history for non-existent order."""
        history = gateway.get_order_history("nonexistent")
        assert len(history) == 0

    def test_get_fill_summary(self, gateway):
        """Test getting fill summary statistics."""
        # Send and fill some orders
        gateway.log_order_sent("1", "AAPL", "buy", "market", 100, 150.0)
        gateway.log_order_filled("1", "AAPL", 100, 150.25)

        gateway.log_order_sent("2", "MSFT", "buy", "market", 50, 300.0)
        gateway.log_order_filled("2", "MSFT", 50, 300.50)

        gateway.log_order_sent("3", "AAPL", "sell", "market", 50, 155.0)
        gateway.log_order_rejected("3", "AAPL", "sell", "market", 50, 155.0, "Rate limit")

        summary = gateway.get_fill_summary()

        assert summary["total_orders"] == 3
        assert summary["filled_orders"] == 2
        assert summary["rejected_orders"] == 1
        assert summary["total_filled_qty"] == 150  # 100 + 50
        assert "AAPL" in summary["by_symbol"]
        assert summary["by_symbol"]["AAPL"]["count"] == 1

    def test_get_recent_events(self, gateway):
        """Test getting recent events."""
        for i in range(15):
            gateway.log_order_sent(
                order_id=str(i),
                symbol="AAPL",
                side="buy",
                order_type="market",
                quantity=10,
                price=150.0,
            )

        recent = gateway.get_recent_events(n=5)
        assert len(recent) == 5
        assert recent[0].order_id == "10"
        assert recent[-1].order_id == "14"

    def test_dry_run_prefix(self, temp_log_file):
        """Test dry run prefix in messages."""
        gateway = OrderGateway(log_file=temp_log_file, dry_run_prefix=True)

        gateway.log_order_sent(
            order_id="123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=100,
            price=150.0,
        )

        assert "DRY_RUN" in gateway._events[0].message

    def test_append_mode(self, temp_log_file):
        """Test append mode preserves existing events."""
        # Create first gateway and log some events
        gateway1 = OrderGateway(log_file=temp_log_file, append=False)
        gateway1.log_order_sent("1", "AAPL", "buy", "market", 100, 150.0)

        # Create second gateway in append mode
        gateway2 = OrderGateway(log_file=temp_log_file, append=True)
        gateway2.log_order_sent("2", "MSFT", "buy", "market", 50, 300.0)

        # Should have loaded previous events
        assert len(gateway2._events) == 2

    def test_clear(self, gateway, temp_log_file):
        """Test clearing events."""
        gateway.log_order_sent("1", "AAPL", "buy", "market", 100, 150.0)
        gateway.log_order_sent("2", "MSFT", "buy", "market", 50, 300.0)

        gateway.clear()

        assert len(gateway._events) == 0

        # File should only have headers
        with open(temp_log_file) as f:
            lines = f.readlines()
            assert len(lines) == 1  # Just header

    def test_creates_directory(self):
        """Test that gateway creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "subdir" / "orders.csv"
            OrderGateway(log_file=str(log_path))

            assert log_path.parent.exists()
            assert log_path.exists()


class TestOrderEventType:
    """Tests for OrderEventType enum."""

    def test_values(self):
        """Test enum values."""
        assert OrderEventType.SENT.value == "SENT"
        assert OrderEventType.MODIFIED.value == "MODIFIED"
        assert OrderEventType.PARTIAL_FILL.value == "PARTIAL_FILL"
        assert OrderEventType.FILLED.value == "FILLED"
        assert OrderEventType.CANCELLED.value == "CANCELLED"
        assert OrderEventType.REJECTED.value == "REJECTED"
