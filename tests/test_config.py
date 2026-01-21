"""Tests for config/trading_config.py."""

import os
import tempfile
from pathlib import Path

import pytest

from config.trading_config import (
    TradingConfig,
    RiskConfig,
    StopLossConfig,
    SymbolConfig,
    LiveEngineConfig,
    DataType,
    AssetType,
)


class TestTradingConfig:
    """Tests for TradingConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        # Clear env vars to ensure defaults
        old_key = os.environ.pop("ALPACA_API_KEY", None)
        old_secret = os.environ.pop("ALPACA_API_SECRET", None)
        try:
            config = TradingConfig()
            assert config.api_key is None
            assert config.api_secret is None
            assert config.paper_mode is True
            assert config.dry_run is False
            assert "paper-api" in config.base_url
        finally:
            if old_key:
                os.environ["ALPACA_API_KEY"] = old_key
            if old_secret:
                os.environ["ALPACA_API_SECRET"] = old_secret

    def test_custom_values(self):
        """Test custom configuration values."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            paper_mode=False,
            dry_run=True,
        )
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.paper_mode is False
        assert config.dry_run is True

    def test_env_loading(self):
        """Test credentials loaded from environment."""
        os.environ["ALPACA_API_KEY"] = "env_key"
        os.environ["ALPACA_API_SECRET"] = "env_secret"
        try:
            config = TradingConfig()
            assert config.api_key == "env_key"
            assert config.api_secret == "env_secret"
        finally:
            del os.environ["ALPACA_API_KEY"]
            del os.environ["ALPACA_API_SECRET"]

    def test_validate_dry_run(self):
        """Test validation passes for dry run without credentials."""
        config = TradingConfig(dry_run=True)
        is_valid, msg = config.validate()
        assert is_valid is True

    def test_validate_missing_credentials(self):
        """Test validation fails when credentials missing."""
        old_key = os.environ.pop("ALPACA_API_KEY", None)
        old_secret = os.environ.pop("ALPACA_API_SECRET", None)
        try:
            config = TradingConfig(dry_run=False)
            is_valid, msg = config.validate()
            assert is_valid is False
        finally:
            if old_key:
                os.environ["ALPACA_API_KEY"] = old_key
            if old_secret:
                os.environ["ALPACA_API_SECRET"] = old_secret


class TestRiskConfig:
    """Tests for RiskConfig."""

    def test_default_values(self):
        """Test default risk configuration."""
        config = RiskConfig()
        assert config.max_position_size == 1000.0
        assert config.max_position_value == 100_000.0
        assert config.max_total_exposure == 500_000.0
        assert config.max_orders_per_minute == 100
        assert config.max_orders_per_symbol_per_minute == 20
        assert config.min_cash_buffer == 1000.0

    def test_custom_values(self):
        """Test custom risk configuration."""
        config = RiskConfig(
            max_position_size=500,
            max_position_value=5000.0,
            max_orders_per_minute=5,
        )
        assert config.max_position_size == 500
        assert config.max_position_value == 5000.0
        assert config.max_orders_per_minute == 5


class TestStopLossConfig:
    """Tests for StopLossConfig."""

    def test_default_values(self):
        """Test default stop loss configuration."""
        config = StopLossConfig()
        assert config.position_stop_pct == 2.0  # 2%
        assert config.trailing_stop_pct == 3.0  # 3%
        assert config.portfolio_stop_pct == 5.0  # 5%
        assert config.max_drawdown_pct == 10.0  # 10%
        assert config.use_trailing_stops is False
        assert config.enable_circuit_breaker is True

    def test_custom_values(self):
        """Test custom stop loss configuration."""
        config = StopLossConfig(
            position_stop_pct=5.0,
            use_trailing_stops=True,
            enable_circuit_breaker=False,
        )
        assert config.position_stop_pct == 5.0
        assert config.use_trailing_stops is True
        assert config.enable_circuit_breaker is False


class TestSymbolConfig:
    """Tests for SymbolConfig."""

    def test_default_values(self):
        """Test default symbol configuration."""
        config = SymbolConfig(symbol="AAPL")
        assert config.symbol == "AAPL"
        assert config.asset_type == AssetType.STOCK
        assert config.data_type is None

    def test_crypto_symbol(self):
        """Test crypto symbol configuration."""
        config = SymbolConfig(
            symbol="BTC/USD",
            asset_type=AssetType.CRYPTO,
            data_type=DataType.TRADES,
        )
        assert config.symbol == "BTC/USD"
        assert config.asset_type == AssetType.CRYPTO
        assert config.data_type == DataType.TRADES


class TestLiveEngineConfig:
    """Tests for LiveEngineConfig."""

    def test_default_values(self):
        """Test default live engine configuration."""
        config = LiveEngineConfig()
        assert config.enable_trading is True
        assert config.enable_stop_loss is True
        assert config.log_orders is True
        assert config.data_type == DataType.TRADES
        assert config.status_log_interval == 100

    def test_from_env(self):
        """Test loading config from environment variables."""
        # Set env vars (using correct names from from_env implementation)
        os.environ["ALPACA_API_KEY"] = "test_key_env"
        os.environ["ALPACA_API_SECRET"] = "test_secret_env"
        os.environ["TRADING_DRY_RUN"] = "true"
        os.environ["TRADING_ENABLE"] = "false"

        try:
            config = LiveEngineConfig.from_env()
            assert config.trading.api_key == "test_key_env"
            assert config.trading.api_secret == "test_secret_env"
            assert config.trading.dry_run is True
            assert config.enable_trading is False
        finally:
            # Clean up
            del os.environ["ALPACA_API_KEY"]
            del os.environ["ALPACA_API_SECRET"]
            del os.environ["TRADING_DRY_RUN"]
            del os.environ["TRADING_ENABLE"]

    def test_from_yaml(self):
        """Test loading config from YAML file."""
        yaml_content = """
trading:
  paper_mode: true
  dry_run: false

risk:
  max_position_size: 500
  max_position_value: 5000.0

stop_loss:
  position_stop_pct: 3.0
  use_trailing_stops: true

enable_trading: false
enable_stop_loss: true
log_orders: false
data_type: quotes
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = LiveEngineConfig.from_yaml(f.name)
                assert config.risk.max_position_size == 500
                assert config.stop_loss.position_stop_pct == 3.0
                assert config.stop_loss.use_trailing_stops is True
                assert config.enable_trading is False
                assert config.log_orders is False
                assert config.data_type == DataType.QUOTES
            finally:
                Path(f.name).unlink()

    def test_from_yaml_missing_file(self):
        """Test error handling for missing YAML file."""
        with pytest.raises(FileNotFoundError):
            LiveEngineConfig.from_yaml("nonexistent.yaml")


class TestDataType:
    """Tests for DataType enum."""

    def test_values(self):
        """Test DataType enum values."""
        assert DataType.TRADES.value == "trades"
        assert DataType.QUOTES.value == "quotes"
        assert DataType.BARS.value == "bars"


class TestAssetType:
    """Tests for AssetType enum."""

    def test_values(self):
        """Test AssetType enum values."""
        assert AssetType.STOCK.value == "stock"
        assert AssetType.CRYPTO.value == "crypto"
