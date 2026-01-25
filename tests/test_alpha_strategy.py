"""
Tests for alpha strategy components.

Tests AlphaLoader, AlphaStrategy, and AlphaConfig.
"""

import pytest
from datetime import datetime, timedelta
import polars as pl

from data_loader.features.alpha_loader import AlphaLoader, AlphaLoaderConfig
from strategy.alpha_strategy import AlphaStrategy, AlphaStrategyConfig
from config.alpha_config import load_alpha_config, parse_alpha_config, save_alpha_config
from models import MarketSnapshot


class TestAlphaLoader:
    """Tests for AlphaLoader class."""

    @pytest.fixture
    def loader(self):
        """Create a loader with default config."""
        config = AlphaLoaderConfig(cache_ttl_minutes=60, lookback_days=252)
        return AlphaLoader(config)

    @pytest.fixture
    def symbols(self):
        """Sample symbols list."""
        return ["AAPL", "MSFT", "GOOGL", "AMZN"]

    def test_load_alpha_returns_polars_df(self, loader, symbols):
        """Test that load_alpha returns a polars DataFrame."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        df = loader.load_alpha("momentum_20d", symbols, start, end)

        assert isinstance(df, pl.DataFrame)
        assert "date" in df.columns
        assert "symbol" in df.columns
        assert "alpha_value" in df.columns

    def test_get_alpha_for_date_returns_dict(self, loader, symbols):
        """Test that get_alpha_for_date returns a dict."""
        date = datetime(2024, 1, 15)

        result = loader.get_alpha_for_date("momentum_20d", symbols, date)

        assert isinstance(result, dict)
        for symbol in symbols:
            assert symbol in result
            assert isinstance(result[symbol], float)

    def test_cache_respects_ttl(self, loader, symbols):
        """Test that cache is used within TTL."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        # First load
        df1 = loader.load_alpha("momentum_20d", symbols, start, end)

        # Second load should use cache
        df2 = loader.load_alpha("momentum_20d", symbols, start, end)

        # Both should return data
        assert not df1.is_empty()
        assert not df2.is_empty()

    def test_builtin_momentum_20d(self, loader, symbols):
        """Test momentum_20d alpha calculation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        df = loader.load_alpha("momentum_20d", symbols, start, end)

        assert not df.is_empty()
        # Should have entries for all symbols
        symbols_in_df = df.select("symbol").unique().to_series().to_list()
        for symbol in symbols:
            assert symbol in symbols_in_df

    def test_builtin_mean_reversion(self, loader, symbols):
        """Test mean_reversion alpha calculation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        df = loader.load_alpha("mean_reversion", symbols, start, end)

        assert not df.is_empty()

    def test_builtin_cross_sectional_momentum(self, loader, symbols):
        """Test cross_sectional_momentum alpha calculation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        df = loader.load_alpha("cross_sectional_momentum", symbols, start, end)

        assert not df.is_empty()

    def test_clear_cache(self, loader, symbols):
        """Test cache clearing."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        # Load data
        loader.load_alpha("momentum_20d", symbols, start, end)
        assert len(loader._cache) > 0

        # Clear specific alpha
        loader.clear_cache("momentum_20d")

        # Load different alpha
        loader.load_alpha("mean_reversion", symbols, start, end)

        # Clear all
        loader.clear_cache()
        assert len(loader._cache) == 0


class TestAlphaStrategy:
    """Tests for AlphaStrategy class."""

    @pytest.fixture
    def symbols(self):
        """Sample symbols list."""
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    @pytest.fixture
    def config(self):
        """Sample strategy config."""
        return AlphaStrategyConfig(
            alpha_names=["momentum_20d"],
            long_threshold=0.3,
            short_threshold=-0.3,
            max_positions=2,
        )

    @pytest.fixture
    def strategy(self, symbols, config):
        """Create a strategy instance."""
        loader = AlphaLoader(AlphaLoaderConfig())
        return AlphaStrategy(symbols, config, loader)

    @pytest.fixture
    def sample_snapshot(self, symbols):
        """Create a sample MarketSnapshot."""
        return MarketSnapshot(
            timestamp=datetime(2024, 1, 15, 10, 30),
            prices={
                "AAPL": 185.50,
                "MSFT": 390.25,
                "GOOGL": 145.00,
                "AMZN": 155.00,
                "META": 375.00,
            },
            bars=None,
        )

    def test_init_with_config(self, strategy, symbols, config):
        """Test strategy initialization."""
        assert strategy.symbols == symbols
        assert strategy.config == config
        assert strategy.alpha_loader is not None

    def test_generate_signals_with_snapshot(self, strategy, sample_snapshot):
        """Test signal generation from snapshot."""
        signals = strategy.generate_signals(sample_snapshot)

        assert isinstance(signals, list)
        # Should have signals for symbols in both snapshot and strategy
        assert len(signals) > 0

        for signal in signals:
            assert "action" in signal
            assert signal["action"] in ["BUY", "SELL", "HOLD"]
            assert "symbol" in signal
            assert "timestamp" in signal

    def test_generate_signals_batch_returns_dict(self, strategy):
        """Test batch signal generation."""
        timestamp = datetime(2024, 1, 15, 10, 30)

        result = strategy.generate_signals_batch(timestamp)

        assert isinstance(result, dict)
        for symbol in strategy.symbols:
            assert symbol in result
            assert "action" in result[symbol]

    def test_refresh_on_new_day(self, strategy, sample_snapshot):
        """Test that alphas refresh on new day."""
        # Generate signals for day 1
        _signals1 = strategy.generate_signals(sample_snapshot)
        first_refresh = strategy._last_refresh

        # Generate signals for same day (should not refresh)
        snapshot_same_day = MarketSnapshot(
            timestamp=sample_snapshot.timestamp + timedelta(hours=2),
            prices=sample_snapshot.prices,
            bars=None,
        )
        strategy.generate_signals(snapshot_same_day)

        # Should still have same refresh time
        assert strategy._last_refresh == first_refresh

        # Generate signals for next day (should refresh)
        snapshot_next_day = MarketSnapshot(
            timestamp=sample_snapshot.timestamp + timedelta(days=1),
            prices=sample_snapshot.prices,
            bars=None,
        )
        strategy.generate_signals(snapshot_next_day)

        # Should have new refresh time
        assert strategy._last_refresh != first_refresh

    def test_threshold_logic(self, strategy, sample_snapshot):
        """Test that thresholds affect signal generation."""
        signals = strategy.generate_signals(sample_snapshot)

        buy_count = sum(1 for s in signals if s["action"] == "BUY")
        sell_count = sum(1 for s in signals if s["action"] == "SELL")

        # With max_positions=2, should have at most 2 buys and 2 sells
        assert buy_count <= strategy.config.max_positions
        assert sell_count <= strategy.config.max_positions

    def test_max_positions_limit(self, symbols):
        """Test that max_positions is respected."""
        config = AlphaStrategyConfig(
            alpha_names=["momentum_20d"],
            long_threshold=0.0,  # Very permissive
            short_threshold=0.0,
            max_positions=1,  # Very restrictive
        )
        strategy = AlphaStrategy(symbols, config, AlphaLoader())

        snapshot = MarketSnapshot(
            timestamp=datetime(2024, 1, 15, 10, 30),
            prices={s: 100.0 for s in symbols},
            bars=None,
        )

        signals = strategy.generate_signals(snapshot)
        buy_count = sum(1 for s in signals if s["action"] == "BUY")

        # Should respect max_positions
        assert buy_count <= config.max_positions

    def test_get_rankings(self, strategy, sample_snapshot):
        """Test getting current rankings."""
        strategy.generate_signals(sample_snapshot)

        rankings = strategy.get_rankings()

        assert isinstance(rankings, list)
        assert len(rankings) == len(strategy.symbols)

        # Should be sorted by alpha descending
        if len(rankings) >= 2:
            assert rankings[0][1] >= rankings[1][1]

    def test_reset(self, strategy, sample_snapshot):
        """Test strategy reset."""
        strategy.generate_signals(sample_snapshot)

        assert strategy._last_refresh is not None
        assert len(strategy._combined_alpha) > 0

        strategy.reset()

        assert strategy._last_refresh is None
        assert len(strategy._combined_alpha) == 0


class TestAlphaConfig:
    """Tests for alpha configuration loading."""

    @pytest.fixture
    def valid_config_dict(self):
        """Valid configuration dictionary."""
        return {
            "strategy": {
                "type": "alpha",
                "alphas": ["momentum_20d", "mean_reversion"],
                "thresholds": {"long": 0.5, "short": -0.5},
                "refresh": "daily",
                "max_positions": 10,
            }
        }

    def test_parse_config(self, valid_config_dict):
        """Test parsing configuration dict."""
        config = parse_alpha_config(valid_config_dict)

        assert config.alpha_names == ["momentum_20d", "mean_reversion"]
        assert config.long_threshold == 0.5
        assert config.short_threshold == -0.5
        assert config.refresh_frequency == "daily"
        assert config.max_positions == 10

    def test_parse_config_defaults(self):
        """Test parsing config with defaults."""
        config = parse_alpha_config({"alphas": ["momentum_20d"]})

        assert config.alpha_names == ["momentum_20d"]
        assert config.long_threshold == 0.5  # Default
        assert config.short_threshold == -0.5  # Default
        assert config.max_positions == 10  # Default

    def test_validation_empty_alphas(self):
        """Test validation rejects empty alphas."""
        with pytest.raises(ValueError, match="At least one alpha"):
            parse_alpha_config({"alphas": []})

    def test_validation_threshold_order(self):
        """Test validation checks threshold order."""
        with pytest.raises(ValueError, match="long_threshold"):
            parse_alpha_config(
                {
                    "alphas": ["momentum_20d"],
                    "thresholds": {"long": -0.5, "short": 0.5},
                }
            )

    def test_validation_refresh_frequency(self):
        """Test validation checks refresh frequency."""
        with pytest.raises(ValueError, match="Invalid refresh"):
            parse_alpha_config(
                {
                    "alphas": ["momentum_20d"],
                    "refresh": "weekly",
                }
            )

    def test_save_and_load_config(self, tmp_path, valid_config_dict):
        """Test saving and loading config."""
        config = parse_alpha_config(valid_config_dict)
        config_path = tmp_path / "alpha_config.yaml"

        save_alpha_config(config, config_path)

        loaded_config = load_alpha_config(config_path)

        assert loaded_config.alpha_names == config.alpha_names
        assert loaded_config.long_threshold == config.long_threshold
        assert loaded_config.max_positions == config.max_positions


@pytest.mark.integration
class TestAlphaStrategyIntegration:
    """Integration tests requiring real data."""

    def test_with_real_quantdl(self):
        """Test with real quantdl client.

        Requires quantdl credentials to be configured.
        """
        # Skip if quantdl not available
        pytest.skip("quantdl integration not yet implemented")
