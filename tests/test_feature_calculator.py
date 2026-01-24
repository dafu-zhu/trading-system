"""
Tests for FeatureCalculator.

Tests technical indicator calculations from Bar data.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from data_loader.features.calculator import FeatureCalculator, FeatureParams
from models import Bar, Timeframe


class TestFeatureCalculator:
    """Tests for FeatureCalculator class."""

    @pytest.fixture
    def sample_bars(self):
        """Create sample bars for testing."""
        from datetime import timedelta
        bars = []
        base_price = 100.0
        base_date = datetime(2024, 1, 1, 9, 30)
        for i in range(50):
            # Create some price variation
            price = base_price + i * 0.5 + (i % 5 - 2) * 0.3
            bars.append(Bar(
                symbol="AAPL",
                timestamp=base_date + timedelta(days=i),
                timeframe=Timeframe.DAY_1,
                open=price - 0.2,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=1000000 + i * 10000,
                vwap=price + 0.1,
                trade_count=50000,
            ))
        return bars

    @pytest.fixture
    def minimal_bars(self):
        """Create minimal bars for edge case testing."""
        return [
            Bar(
                symbol="TEST",
                timestamp=datetime(2024, 1, 1, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=100, high=101, low=99, close=100.5, volume=1000000,
            ),
            Bar(
                symbol="TEST",
                timestamp=datetime(2024, 1, 2, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=100.5, high=102, low=100, close=101.5, volume=1100000,
            ),
            Bar(
                symbol="TEST",
                timestamp=datetime(2024, 1, 3, 9, 30),
                timeframe=Timeframe.DAY_1,
                open=101.5, high=103, low=101, close=102.5, volume=1200000,
            ),
        ]


class TestBarsToDataframe(TestFeatureCalculator):
    """Tests for bars_to_dataframe conversion."""

    def test_conversion(self, sample_bars):
        """Test basic conversion."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)

        assert len(df) == len(sample_bars)
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert df.index.name == 'timestamp'

    def test_optional_fields(self, sample_bars):
        """Test that optional fields are included."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)

        assert 'vwap' in df.columns
        assert 'trade_count' in df.columns

    def test_empty_bars(self):
        """Test conversion with empty list."""
        df = FeatureCalculator.bars_to_dataframe([])
        assert df.empty

    def test_bars_sorted(self, sample_bars):
        """Test that result is sorted by timestamp."""
        # Shuffle bars
        import random
        shuffled = sample_bars.copy()
        random.shuffle(shuffled)

        df = FeatureCalculator.bars_to_dataframe(shuffled)

        # Should be sorted
        assert df.index.is_monotonic_increasing


class TestMACDCalculation(TestFeatureCalculator):
    """Tests for MACD calculation."""

    def test_macd_columns(self, sample_bars):
        """Test MACD adds correct columns."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_macd(df)

        assert 'macd' in df.columns
        assert 'macd_signal' in df.columns
        assert 'macd_histogram' in df.columns

    def test_macd_custom_params(self, sample_bars):
        """Test MACD with custom parameters."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_macd(df, fast_period=8, slow_period=21, signal_period=5)

        assert 'macd' in df.columns
        # Values should be different from defaults
        df2 = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_macd(df2)  # Default params
        assert not df['macd'].equals(df2['macd'])

    def test_macd_histogram_equals_diff(self, sample_bars):
        """Test that histogram = macd - signal."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_macd(df)

        expected_histogram = df['macd'] - df['macd_signal']
        pd.testing.assert_series_equal(
            df['macd_histogram'],
            expected_histogram,
            check_names=False,
        )


class TestRSICalculation(TestFeatureCalculator):
    """Tests for RSI calculation."""

    def test_rsi_column(self, sample_bars):
        """Test RSI adds correct column."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_rsi(df)

        assert 'rsi' in df.columns

    def test_rsi_range(self, sample_bars):
        """Test RSI values are in valid range [0, 100]."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_rsi(df)

        # Drop NaN values (initial window)
        rsi_values = df['rsi'].dropna()
        assert (rsi_values >= 0).all()
        assert (rsi_values <= 100).all()

    def test_rsi_custom_window(self, sample_bars):
        """Test RSI with custom window."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_rsi(df, window=21)

        assert 'rsi' in df.columns


class TestMovingAverages(TestFeatureCalculator):
    """Tests for moving average calculation."""

    def test_ma_columns(self, sample_bars):
        """Test MA adds correct columns."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_moving_averages(df, windows=(5, 10, 20))

        assert 'sma_5' in df.columns
        assert 'ema_5' in df.columns
        assert 'sma_10' in df.columns
        assert 'ema_10' in df.columns
        assert 'sma_20' in df.columns
        assert 'ema_20' in df.columns

    def test_sma_calculation(self, sample_bars):
        """Test SMA calculation is correct."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_moving_averages(df, windows=(5,))

        # Manual calculation for last value
        expected_sma = df['close'].iloc[-5:].mean()
        assert abs(df['sma_5'].iloc[-1] - expected_sma) < 0.0001


class TestBollingerBands(TestFeatureCalculator):
    """Tests for Bollinger Bands calculation."""

    def test_bb_columns(self, sample_bars):
        """Test BB adds correct columns."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_bollinger_bands(df)

        assert 'bb_middle' in df.columns
        assert 'bb_upper' in df.columns
        assert 'bb_lower' in df.columns
        assert 'bb_width' in df.columns
        assert 'bb_position' in df.columns

    def test_bb_relationships(self, sample_bars):
        """Test BB band relationships."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_bollinger_bands(df)

        # Upper should be above middle, lower should be below
        valid_rows = df.dropna()
        assert (valid_rows['bb_upper'] >= valid_rows['bb_middle']).all()
        assert (valid_rows['bb_lower'] <= valid_rows['bb_middle']).all()

        # Width should equal upper - lower
        expected_width = valid_rows['bb_upper'] - valid_rows['bb_lower']
        pd.testing.assert_series_equal(
            valid_rows['bb_width'],
            expected_width,
            check_names=False,
        )


class TestATRCalculation(TestFeatureCalculator):
    """Tests for ATR calculation."""

    def test_atr_column(self, sample_bars):
        """Test ATR adds correct column."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_atr(df)

        assert 'atr' in df.columns

    def test_atr_positive(self, sample_bars):
        """Test ATR values are positive."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_atr(df)

        atr_values = df['atr'].dropna()
        assert (atr_values >= 0).all()


class TestReturnsCalculation(TestFeatureCalculator):
    """Tests for returns calculation."""

    def test_returns_columns(self, sample_bars):
        """Test returns adds correct columns."""
        df = FeatureCalculator.bars_to_dataframe(sample_bars)
        FeatureCalculator.add_returns(df)

        assert 'returns' in df.columns
        assert 'log_returns' in df.columns


class TestCalculateMethod(TestFeatureCalculator):
    """Tests for the calculate method."""

    def test_calculate_single_feature(self, sample_bars):
        """Test calculating a single feature."""
        df = FeatureCalculator.calculate(sample_bars, ['macd'])

        assert 'macd' in df.columns
        assert 'rsi' not in df.columns

    def test_calculate_multiple_features(self, sample_bars):
        """Test calculating multiple features."""
        df = FeatureCalculator.calculate(sample_bars, ['macd', 'rsi', 'returns'])

        assert 'macd' in df.columns
        assert 'rsi' in df.columns
        assert 'returns' in df.columns

    def test_calculate_with_params(self, sample_bars):
        """Test calculating with custom params."""
        params = FeatureParams(
            macd_fast=8,
            macd_slow=21,
            rsi_window=21,
        )
        df = FeatureCalculator.calculate(sample_bars, ['macd', 'rsi'], params)

        assert 'macd' in df.columns
        assert 'rsi' in df.columns

    def test_calculate_unknown_feature(self, sample_bars):
        """Test that unknown feature raises error."""
        with pytest.raises(ValueError, match="Unknown feature"):
            FeatureCalculator.calculate(sample_bars, ['unknown_feature'])


class TestCalculateAllMethod(TestFeatureCalculator):
    """Tests for the calculate_all method."""

    def test_calculate_all(self, sample_bars):
        """Test calculating all features."""
        df = FeatureCalculator.calculate_all(sample_bars)

        # Should have all indicator types
        assert 'macd' in df.columns
        assert 'rsi' in df.columns
        assert 'returns' in df.columns
        assert 'atr' in df.columns
        assert 'bb_middle' in df.columns


class TestFeatureParams:
    """Tests for FeatureParams dataclass."""

    def test_default_params(self):
        """Test default parameter values."""
        params = FeatureParams()

        assert params.macd_fast == 12
        assert params.macd_slow == 26
        assert params.macd_signal == 9
        assert params.rsi_window == 14
        assert params.bb_window == 20
        assert params.bb_std == 2.0
        assert params.atr_window == 14

    def test_custom_params(self):
        """Test custom parameter values."""
        params = FeatureParams(
            macd_fast=8,
            macd_slow=21,
            macd_signal=5,
            rsi_window=21,
        )

        assert params.macd_fast == 8
        assert params.macd_slow == 21
        assert params.macd_signal == 5
        assert params.rsi_window == 21
