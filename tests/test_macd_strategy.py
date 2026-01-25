"""
Tests for MACDStrategy.

Tests with mocked DataGateway for unit testing.
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock

from strategy.macd_strategy import MACDStrategy
from models import DataGateway, Timeframe, Bar, MarketSnapshot


class TestMACDStrategy:
    """Tests for MACDStrategy class."""

    @pytest.fixture
    def sample_bars(self):
        """Create sample bars with price movement for MACD testing."""
        from datetime import timedelta

        # Generate bars with a pattern that will produce MACD crossovers
        bars = []
        base_price = 100.0
        base_date = datetime(2024, 1, 1, 9, 30)
        # First 26 bars: upward trend
        for i in range(40):
            if i < 15:
                price = base_price + i * 0.5  # Uptrend
            elif i < 25:
                price = base_price + 15 * 0.5 - (i - 15) * 0.3  # Downtrend
            else:
                price = base_price + (i - 25) * 0.6  # Another uptrend

            bars.append(
                Bar(
                    symbol="AAPL",
                    timestamp=base_date + timedelta(days=i),
                    timeframe=Timeframe.DAY_1,
                    open=price - 0.5,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price,
                    volume=1000000,
                )
            )
        return bars

    @pytest.fixture
    def mock_gateway(self, sample_bars):
        """Create a mock DataGateway."""
        gateway = MagicMock(spec=DataGateway)
        gateway.fetch_bars.return_value = sample_bars
        gateway.is_connected.return_value = True
        return gateway

    @pytest.fixture
    def strategy(self, mock_gateway):
        """Create a strategy with mock gateway."""
        return MACDStrategy(
            gateway=mock_gateway,
            timeframe=Timeframe.DAY_1,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        )

    def test_init(self, mock_gateway):
        """Test strategy initialization."""
        strategy = MACDStrategy(
            gateway=mock_gateway,
            timeframe=Timeframe.HOUR_1,
            fast_period=8,
            slow_period=21,
            signal_period=5,
        )

        assert strategy.gateway == mock_gateway
        assert strategy.timeframe == Timeframe.HOUR_1
        assert strategy._fast_period == 8
        assert strategy._slow_period == 21
        assert strategy._signal_period == 5

    def test_get_data(self, strategy, mock_gateway, sample_bars):
        """Test data loading with MACD calculation."""
        df = strategy.get_data(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 2, 15),
        )

        # Should have called gateway
        mock_gateway.fetch_bars.assert_called_once()

        # Should have MACD columns
        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_histogram" in df.columns
        assert "signal" in df.columns

        # Should have data
        assert len(df) == len(sample_bars)

    def test_get_data_empty(self, mock_gateway):
        """Test get_data with empty bars."""
        mock_gateway.fetch_bars.return_value = []

        strategy = MACDStrategy(gateway=mock_gateway)
        df = strategy.get_data("AAPL", datetime(2024, 1, 1), datetime(2024, 2, 1))

        assert df.empty

    def test_generate_signals(self, strategy, sample_bars):
        """Test signal generation for a snapshot."""
        # First load data
        strategy.get_data("AAPL", datetime(2024, 1, 1), datetime(2024, 2, 15))

        # Generate signal for a known timestamp using MarketSnapshot
        snapshot = MarketSnapshot(
            timestamp=sample_bars[30].timestamp,
            prices={"AAPL": sample_bars[30].close},
            bars={"AAPL": sample_bars[30]},
        )

        signals = strategy.generate_signals(snapshot)

        assert len(signals) == 1
        assert signals[0]["symbol"] == "AAPL"
        assert signals[0]["action"] in ["BUY", "SELL", "HOLD"]
        assert signals[0]["timestamp"] == snapshot.timestamp
        assert signals[0]["price"] == sample_bars[30].close

    def test_generate_signals_unknown_timestamp(self, strategy, sample_bars):
        """Test signal generation for timestamp not in data."""
        # Load data
        strategy.get_data("AAPL", datetime(2024, 1, 1), datetime(2024, 2, 15))

        # Generate signal for timestamp not in data (between bars)
        snapshot = MarketSnapshot(
            timestamp=datetime(2024, 1, 15, 12, 0),  # Mid-day, not in data
            prices={"AAPL": 105.0},
            bars=None,
        )

        signals = strategy.generate_signals(snapshot)

        assert len(signals) == 1
        # Should find closest prior timestamp
        assert signals[0]["action"] in ["BUY", "SELL", "HOLD"]

    def test_generate_signals_loads_data_if_needed(self, strategy, mock_gateway):
        """Test that generate_signals loads data if not cached."""
        snapshot = MarketSnapshot(
            timestamp=datetime(2024, 1, 15, 9, 30),
            prices={"AAPL": 105.0},
            bars=None,
        )

        signals = strategy.generate_signals(snapshot)

        # Should have called gateway to load data
        mock_gateway.fetch_bars.assert_called()
        assert len(signals) == 1

    def test_generate_signals_batch(self, strategy, sample_bars):
        """Test batch signal generation."""
        df = strategy.generate_signals_batch(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 2, 15),
        )

        assert "signal" in df.columns
        assert len(df) == len(sample_bars)

        # Check signal distribution
        signal_counts = df["signal"].value_counts()
        assert "HOLD" in signal_counts.index  # Should have some HOLDs

    def test_clear_cache(self, strategy, mock_gateway):
        """Test cache clearing."""
        from datetime import timedelta

        base_date = datetime(2024, 1, 1, 9, 30)
        # Load data for two symbols
        strategy.get_data("AAPL", datetime(2024, 1, 1), datetime(2024, 2, 15))
        mock_gateway.fetch_bars.return_value = [
            Bar(
                symbol="MSFT",
                timestamp=base_date + timedelta(days=i),
                timeframe=Timeframe.DAY_1,
                open=300 + i,
                high=305 + i,
                low=298 + i,
                close=302 + i,
                volume=500000,
            )
            for i in range(40)
        ]
        strategy.get_data("MSFT", datetime(2024, 1, 1), datetime(2024, 2, 15))

        assert "AAPL" in strategy._data_cache
        assert "MSFT" in strategy._data_cache

        # Clear specific symbol
        strategy.clear_cache("AAPL")
        assert "AAPL" not in strategy._data_cache
        assert "MSFT" in strategy._data_cache

        # Clear all
        strategy.clear_cache()
        assert len(strategy._data_cache) == 0

    def test_signal_values(self, strategy, sample_bars):
        """Test that signals have valid values."""
        df = strategy.get_data("AAPL", datetime(2024, 1, 1), datetime(2024, 2, 15))

        valid_signals = {"BUY", "SELL", "HOLD"}
        for signal in df["signal"]:
            assert signal in valid_signals

    def test_default_timeframe(self, mock_gateway):
        """Test default timeframe is daily."""
        strategy = MACDStrategy(gateway=mock_gateway)
        assert strategy.timeframe == Timeframe.DAY_1


class TestMACDStrategyIntegration:
    """Integration tests with real calculations."""

    @pytest.fixture
    def realistic_bars(self):
        """Create realistic price data with clear MACD crossovers."""
        import math
        from datetime import timedelta

        bars = []
        base_date = datetime(2024, 1, 1, 9, 30)
        # Create a sinusoidal price pattern that will produce clear crossovers
        for i in range(100):
            # Sin wave with period ~40 bars
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

    def test_crossover_detection(self, realistic_bars):
        """Test that strategy detects MACD crossovers."""
        gateway = MagicMock(spec=DataGateway)
        gateway.fetch_bars.return_value = realistic_bars

        strategy = MACDStrategy(gateway=gateway)
        df = strategy.get_data("TEST", datetime(2024, 1, 1), datetime(2024, 4, 30))

        # Should have some BUY and SELL signals with sinusoidal data
        buy_count = (df["signal"] == "BUY").sum()
        sell_count = (df["signal"] == "SELL").sum()

        # With 100 bars of sinusoidal data, we should see crossovers
        # (At least 1 of each, but likely more)
        assert buy_count > 0, "Should detect at least one bullish crossover"
        assert sell_count > 0, "Should detect at least one bearish crossover"


class TestGenerateSignalsFromMACD:
    """Tests for the generate_signals_from_macd static method."""

    def test_signal_generation(self):
        """Test signal generation adds signal column."""
        df = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "macd": [1, 2, 1, 0, 1],
                "macd_signal": [0.5, 1.5, 1.5, 0.5, 0.5],
            }
        )

        result = MACDStrategy.generate_signals_from_macd(df)

        assert "signal" in result.columns
        assert set(result["signal"].unique()).issubset({"BUY", "SELL", "HOLD"})

    def test_requires_macd_columns(self):
        """Test that signal generation requires MACD columns."""
        df = pd.DataFrame({"close": [100, 101, 102]})

        with pytest.raises(ValueError, match="Missing columns"):
            MACDStrategy.generate_signals_from_macd(df)

    def test_signal_logic(self):
        """Test signal logic with known values."""
        df = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "macd": [1, 2, -1, -2, 1],
                "macd_signal": [0.5, 1.5, 0, -1, 0.5],
            }
        )

        result = MACDStrategy.generate_signals_from_macd(df)

        # Row 2: macd goes from above signal (2 > 1.5) to below (-1 < 0) -> SELL
        assert result.iloc[2]["signal"] == "SELL"
        # Row 4: macd goes from below signal (-2 < -1) to above (1 > 0.5) -> BUY
        assert result.iloc[4]["signal"] == "BUY"
