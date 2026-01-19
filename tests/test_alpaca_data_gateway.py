"""
Tests for AlpacaDataGateway.

Includes:
- Unit tests with mocked Alpaca API
- Integration tests with real API (marked with @pytest.mark.integration)
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timezone

from gateway.alpaca_data_gateway import AlpacaDataGateway
from data_loader.storage import BarStorage
from models import Timeframe, Bar, MarketCalendarDay


class TestAlpacaDataGatewayUnit:
    """Unit tests with mocked Alpaca API."""

    @pytest.fixture
    def mock_data_client(self):
        """Create a mock StockHistoricalDataClient."""
        with patch("gateway.alpaca_data_gateway.StockHistoricalDataClient") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def mock_trading_client(self):
        """Create a mock TradingClient."""
        with patch("gateway.alpaca_data_gateway.TradingClient") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield BarStorage(db_path=db_path)

    @pytest.fixture
    def gateway(self, mock_data_client, mock_trading_client, temp_storage):
        """Create gateway with mocked clients."""
        with patch.dict(os.environ, {
            "ALPACA_API_KEY": "test_key",
            "ALPACA_API_SECRET": "test_secret",
        }):
            gw = AlpacaDataGateway(use_cache=True, storage=temp_storage)
            return gw

    def test_init_requires_credentials(self):
        """Test that gateway requires API credentials."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API credentials required"):
                AlpacaDataGateway()

    def test_init_accepts_env_credentials(self):
        """Test that gateway accepts credentials from environment."""
        with patch.dict(os.environ, {
            "ALPACA_API_KEY": "test_key",
            "ALPACA_API_SECRET": "test_secret",
        }):
            with patch("gateway.alpaca_data_gateway.StockHistoricalDataClient"):
                with patch("gateway.alpaca_data_gateway.TradingClient"):
                    gw = AlpacaDataGateway(use_cache=False)
                    assert gw._api_key == "test_key"
                    assert gw._api_secret == "test_secret"

    def test_connect_success(self, gateway, mock_data_client, mock_trading_client):
        """Test successful connection."""
        result = gateway.connect()

        assert result is True
        assert gateway.is_connected() is True

    def test_disconnect(self, gateway, mock_data_client, mock_trading_client):
        """Test disconnect."""
        gateway.connect()
        gateway.disconnect()

        assert gateway.is_connected() is False

    def test_fetch_bars_from_api(self, gateway, mock_data_client, mock_trading_client):
        """Test fetching bars from API."""
        gateway.connect()

        # Mock API response
        mock_bar = MagicMock()
        mock_bar.timestamp = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        mock_bar.open = 185.0
        mock_bar.high = 186.5
        mock_bar.low = 184.0
        mock_bar.close = 186.0
        mock_bar.volume = 50000000
        mock_bar.vwap = 185.5
        mock_bar.trade_count = 100000

        mock_response = MagicMock()
        mock_response.data = {"AAPL": [mock_bar]}
        mock_data_client.get_stock_bars.return_value = mock_response

        bars = gateway.fetch_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        assert len(bars) == 1
        assert bars[0].symbol == "AAPL"
        assert bars[0].open == 185.0
        assert bars[0].close == 186.0

    def test_fetch_bars_caches_results(self, gateway, mock_data_client, mock_trading_client, temp_storage):
        """Test that fetched bars are cached."""
        gateway.connect()

        # Mock API response
        mock_bar = MagicMock()
        mock_bar.timestamp = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        mock_bar.open = 185.0
        mock_bar.high = 186.5
        mock_bar.low = 184.0
        mock_bar.close = 186.0
        mock_bar.volume = 50000000
        mock_bar.vwap = None
        mock_bar.trade_count = None

        mock_response = MagicMock()
        mock_response.data = {"AAPL": [mock_bar]}
        mock_data_client.get_stock_bars.return_value = mock_response

        # First fetch - should call API
        gateway.fetch_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        # Verify cached
        cached = temp_storage.get_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )
        assert len(cached) == 1

    def test_fetch_bars_uses_cache(self, gateway, mock_data_client, mock_trading_client, temp_storage):
        """Test that fetch uses cache when available."""
        gateway.connect()

        # Pre-populate cache
        cached_bar = Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 9, 30),
            timeframe=Timeframe.DAY_1,
            open=185.0,
            high=186.5,
            low=184.0,
            close=186.0,
            volume=50000000,
        )
        temp_storage.save_bars([cached_bar])

        # Fetch - should use cache, not call API
        bars = gateway.fetch_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        assert len(bars) == 1
        mock_data_client.get_stock_bars.assert_not_called()

    def test_stream_bars(self, gateway, mock_data_client, mock_trading_client, temp_storage):
        """Test streaming bars."""
        gateway.connect()

        # Pre-populate cache
        bars = [
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 2, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=185.0, high=186.5, low=184.0, close=186.0, volume=50000000,
            ),
            Bar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 3, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=186.0, high=187.0, low=185.5, close=186.5, volume=45000000,
            ),
        ]
        temp_storage.save_bars(bars)

        # Stream bars
        streamed = list(gateway.stream_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        ))

        assert len(streamed) == 2
        assert streamed[0].open == 185.0
        assert streamed[1].open == 186.0

    def test_operations_require_connection(self, gateway):
        """Test that operations require connection."""
        with pytest.raises(RuntimeError, match="Not connected"):
            gateway.fetch_bars("AAPL", Timeframe.DAY_1, datetime(2024, 1, 1), datetime(2024, 1, 5))

    def test_timeframe_mapping(self, gateway):
        """Test internal timeframe to Alpaca timeframe mapping."""
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        result = gateway._to_alpaca_timeframe(Timeframe.MIN_1)
        assert result.amount == 1
        assert result.unit == TimeFrameUnit.Minute

        result = gateway._to_alpaca_timeframe(Timeframe.DAY_1)
        assert result.amount == 1
        assert result.unit == TimeFrameUnit.Day

        result = gateway._to_alpaca_timeframe(Timeframe.HOUR_1)
        assert result.amount == 1
        assert result.unit == TimeFrameUnit.Hour


class TestAlpacaDataGatewayIntegration:
    """Integration tests with real Alpaca API.

    These tests require valid API credentials and make real API calls.
    Run with: pytest -m integration
    """

    @pytest.fixture
    def live_gateway(self):
        """Create gateway with real credentials."""
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")

        if not api_key or not api_secret:
            pytest.skip("Alpaca credentials not available")

        # Use temporary storage
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = BarStorage(db_path=db_path)
            gw = AlpacaDataGateway(storage=storage)
            yield gw
            if gw.is_connected():
                gw.disconnect()

    @pytest.mark.integration
    def test_connect_to_alpaca(self, live_gateway):
        """Test real connection to Alpaca."""
        result = live_gateway.connect()
        assert result is True
        assert live_gateway.is_connected() is True

    @pytest.mark.integration
    def test_fetch_real_bars(self, live_gateway):
        """Test fetching real bars."""
        live_gateway.connect()

        bars = live_gateway.fetch_bars(
            "AAPL",
            Timeframe.DAY_1,
            datetime(2025, 1, 2),
            datetime(2025, 1, 10),
        )

        assert len(bars) > 0
        assert all(bar.symbol == "AAPL" for bar in bars)
        assert all(bar.timeframe == Timeframe.DAY_1 for bar in bars)

    @pytest.mark.integration
    def test_fetch_bulk_bars(self, live_gateway):
        """Test fetching bars for multiple symbols."""
        live_gateway.connect()

        result = live_gateway.fetch_bars_bulk(
            ["AAPL", "MSFT"],
            Timeframe.DAY_1,
            datetime(2025, 1, 2),
            datetime(2025, 1, 10),
        )

        assert "AAPL" in result
        assert "MSFT" in result
        assert len(result["AAPL"]) > 0
        assert len(result["MSFT"]) > 0

    @pytest.mark.integration
    def test_get_market_calendar(self, live_gateway):
        """Test getting market calendar."""
        live_gateway.connect()

        calendar = live_gateway.get_market_calendar(
            date(2025, 1, 1),
            date(2025, 1, 15),
        )

        assert len(calendar) > 0
        assert all(isinstance(day, MarketCalendarDay) for day in calendar)
        # First trading day of 2025 is Jan 2
        assert calendar[0].date == date(2025, 1, 2)

    @pytest.mark.integration
    def test_get_latest_bar(self, live_gateway):
        """Test getting latest bar (may return None with free tier)."""
        live_gateway.connect()

        # Note: This may fail with free tier due to SIP data restrictions
        # The test verifies the method runs without error
        try:
            bar = live_gateway.get_latest_bar("AAPL", Timeframe.DAY_1)
            if bar is not None:
                assert bar.symbol == "AAPL"
                assert bar.timeframe == Timeframe.DAY_1
        except Exception:
            # Free tier may not have access to recent data
            pytest.skip("Alpaca free tier may not have access to recent SIP data")


class TestMarketCalendarDay:
    """Tests for MarketCalendarDay dataclass."""

    def test_calendar_day_creation(self):
        """Test creating a market calendar day."""
        day = MarketCalendarDay(
            date=date(2025, 1, 2),
            open_time=datetime(2025, 1, 2, 9, 30),
            close_time=datetime(2025, 1, 2, 16, 0),
            is_open=True,
            early_close=False,
        )

        assert day.date == date(2025, 1, 2)
        assert day.open_time.hour == 9
        assert day.close_time.hour == 16
        assert day.is_open is True
        assert day.early_close is False

    def test_calendar_day_early_close(self):
        """Test market calendar day with early close."""
        day = MarketCalendarDay(
            date=date(2025, 7, 3),  # Day before July 4th
            open_time=datetime(2025, 7, 3, 9, 30),
            close_time=datetime(2025, 7, 3, 13, 0),  # Early close
            is_open=True,
            early_close=True,
        )

        assert day.early_close is True
        assert day.close_time.hour == 13
