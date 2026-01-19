"""
Tests for BarStorage.

Tests SQLite storage for OHLCV bar data.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from data_loader.storage import BarStorage
from models import Bar, Timeframe


class TestBarStorage:
    """Tests for BarStorage class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield db_path

    @pytest.fixture
    def storage(self, temp_db):
        """Create a BarStorage instance with temporary database."""
        return BarStorage(db_path=temp_db)

    @pytest.fixture
    def sample_bars(self):
        """Create sample bars for testing."""
        return [
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 2, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=185.0,
                high=186.5,
                low=184.0,
                close=186.0,
                volume=50000000,
                vwap=185.5,
                trade_count=100000,
            ),
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 3, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=186.0,
                high=187.0,
                low=185.5,
                close=186.5,
                volume=45000000,
                vwap=186.2,
                trade_count=90000,
            ),
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 4, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=186.5,
                high=188.0,
                low=186.0,
                close=187.5,
                volume=55000000,
                vwap=187.0,
                trade_count=110000,
            ),
        ]

    def test_init_creates_database(self, storage, temp_db):
        """Test that init creates the database file."""
        assert temp_db.exists()

    def test_save_bars(self, storage, sample_bars):
        """Test saving bars to database."""
        count = storage.save_bars(sample_bars)
        assert count == 3

    def test_save_empty_bars(self, storage):
        """Test saving empty list returns 0."""
        count = storage.save_bars([])
        assert count == 0

    def test_get_bars(self, storage, sample_bars):
        """Test retrieving bars from database."""
        storage.save_bars(sample_bars)

        bars = storage.get_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        assert len(bars) == 3
        assert bars[0].symbol == "AAPL"
        assert bars[0].open == 185.0
        assert bars[2].close == 187.5

    def test_get_bars_empty_result(self, storage):
        """Test getting bars when no data exists."""
        bars = storage.get_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )
        assert bars == []

    def test_get_bars_date_range(self, storage, sample_bars):
        """Test that date range filtering works correctly."""
        storage.save_bars(sample_bars)

        # Get only first two bars
        bars = storage.get_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 2),
            datetime(2024, 1, 4),
        )

        assert len(bars) == 2
        assert bars[0].timestamp == datetime(2024, 1, 2, 9, 30)
        assert bars[1].timestamp == datetime(2024, 1, 3, 9, 30)

    def test_get_latest_timestamp(self, storage, sample_bars):
        """Test getting latest timestamp."""
        storage.save_bars(sample_bars)

        latest = storage.get_latest_timestamp("AAPL", Timeframe.DAY_1)

        assert latest == datetime(2024, 1, 4, 9, 30)

    def test_get_latest_timestamp_no_data(self, storage):
        """Test getting latest timestamp when no data exists."""
        latest = storage.get_latest_timestamp("AAPL", Timeframe.DAY_1)
        assert latest is None

    def test_get_earliest_timestamp(self, storage, sample_bars):
        """Test getting earliest timestamp."""
        storage.save_bars(sample_bars)

        earliest = storage.get_earliest_timestamp("AAPL", Timeframe.DAY_1)

        assert earliest == datetime(2024, 1, 2, 9, 30)

    def test_has_data(self, storage, sample_bars):
        """Test checking if data exists."""
        storage.save_bars(sample_bars)

        assert storage.has_data(
            "AAPL", Timeframe.DAY_1,
            datetime(2024, 1, 1), datetime(2024, 1, 5)
        )
        assert not storage.has_data(
            "AAPL", Timeframe.DAY_1,
            datetime(2024, 2, 1), datetime(2024, 2, 5)
        )
        assert not storage.has_data(
            "MSFT", Timeframe.DAY_1,
            datetime(2024, 1, 1), datetime(2024, 1, 5)
        )

    def test_get_bar_count(self, storage, sample_bars):
        """Test getting bar count."""
        storage.save_bars(sample_bars)

        count = storage.get_bar_count("AAPL", Timeframe.DAY_1)
        assert count == 3

        count = storage.get_bar_count("MSFT", Timeframe.DAY_1)
        assert count == 0

    def test_get_symbols(self, storage, sample_bars):
        """Test getting all symbols."""
        storage.save_bars(sample_bars)

        # Add another symbol
        msft_bar = Bar(
            symbol="MSFT",
            timestamp=datetime(2024, 1, 2, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=370.0,
            high=375.0,
            low=369.0,
            close=374.0,
            volume=20000000,
        )
        storage.save_bars([msft_bar])

        symbols = storage.get_symbols()
        assert set(symbols) == {"AAPL", "MSFT"}

    def test_get_timeframes(self, storage, sample_bars):
        """Test getting timeframes for a symbol."""
        storage.save_bars(sample_bars)

        # Add hourly bar
        hourly_bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 10, 0),
            timeframe=Timeframe.HOUR_1,
            open=185.0,
            high=186.0,
            low=185.0,
            close=185.5,
            volume=5000000,
        )
        storage.save_bars([hourly_bar])

        timeframes = storage.get_timeframes("AAPL")
        assert Timeframe.DAY_1 in timeframes
        assert Timeframe.HOUR_1 in timeframes

    def test_delete_bars(self, storage, sample_bars):
        """Test deleting bars."""
        storage.save_bars(sample_bars)
        assert storage.get_bar_count("AAPL", Timeframe.DAY_1) == 3

        deleted = storage.delete_bars("AAPL", Timeframe.DAY_1)
        assert deleted == 3
        assert storage.get_bar_count("AAPL", Timeframe.DAY_1) == 0

    def test_delete_bars_all_timeframes(self, storage, sample_bars):
        """Test deleting all bars for a symbol."""
        storage.save_bars(sample_bars)

        # Add hourly bar
        hourly_bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 10, 0),
            timeframe=Timeframe.HOUR_1,
            open=185.0,
            high=186.0,
            low=185.0,
            close=185.5,
            volume=5000000,
        )
        storage.save_bars([hourly_bar])

        # Delete all AAPL bars
        deleted = storage.delete_bars("AAPL")
        assert deleted == 4
        assert storage.get_bar_count("AAPL", Timeframe.DAY_1) == 0
        assert storage.get_bar_count("AAPL", Timeframe.HOUR_1) == 0

    def test_upsert_bars(self, storage, sample_bars):
        """Test that saving duplicate bars updates them."""
        storage.save_bars(sample_bars)

        # Modify and re-save first bar
        modified_bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=185.0,
            high=190.0,  # Changed
            low=184.0,
            close=189.0,  # Changed
            volume=60000000,  # Changed
        )
        storage.save_bars([modified_bar])

        # Should still have 3 bars (not 4)
        assert storage.get_bar_count("AAPL", Timeframe.DAY_1) == 3

        # Retrieve and check updated values
        bars = storage.get_bars(
            "AAPL", Timeframe.DAY_1,
            datetime(2024, 1, 2), datetime(2024, 1, 3)
        )
        assert bars[0].high == 190.0
        assert bars[0].close == 189.0
        assert bars[0].volume == 60000000

    def test_get_stats(self, storage, sample_bars):
        """Test getting storage statistics."""
        storage.save_bars(sample_bars)

        stats = storage.get_stats()

        assert stats["total_bars"] == 3
        assert stats["symbols"] == 1
        assert "db_path" in stats
        assert "db_size_mb" in stats

    def test_bars_sorted_by_timestamp(self, storage):
        """Test that retrieved bars are sorted by timestamp."""
        # Insert bars out of order
        bars = [
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 3, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=186.0, high=187.0, low=185.5, close=186.5, volume=45000000,
            ),
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 2, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=185.0, high=186.5, low=184.0, close=186.0, volume=50000000,
            ),
        ]
        storage.save_bars(bars)

        retrieved = storage.get_bars(
            "AAPL", Timeframe.DAY_1,
            datetime(2024, 1, 1), datetime(2024, 1, 5)
        )

        assert retrieved[0].timestamp < retrieved[1].timestamp


class TestTimeframeEnum:
    """Tests for Timeframe enum."""

    def test_timeframe_values(self):
        """Test timeframe values."""
        assert Timeframe.MIN_1.value == "1Min"
        assert Timeframe.DAY_1.value == "1Day"
        assert Timeframe.WEEK_1.value == "1Week"

    def test_timeframe_from_value(self):
        """Test creating timeframe from value."""
        assert Timeframe("1Day") == Timeframe.DAY_1
        assert Timeframe("1Hour") == Timeframe.HOUR_1


class TestBarDataclass:
    """Tests for Bar dataclass."""

    def test_bar_creation(self):
        """Test creating a bar."""
        bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=185.0,
            high=186.5,
            low=184.0,
            close=186.0,
            volume=50000000,
        )

        assert bar.symbol == "AAPL"
        assert bar.open == 185.0
        assert bar.vwap is None
        assert bar.trade_count is None

    def test_bar_with_optional_fields(self):
        """Test creating a bar with optional fields."""
        bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=185.0,
            high=186.5,
            low=184.0,
            close=186.0,
            volume=50000000,
            vwap=185.5,
            trade_count=100000,
        )

        assert bar.vwap == 185.5
        assert bar.trade_count == 100000
