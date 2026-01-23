"""
Trading configuration dataclasses.

Provides unified configuration for live trading including API credentials,
risk parameters, stop-loss settings, and engine options.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class DataType(Enum):
    """Type of market data stream."""

    TRADES = "trades"
    QUOTES = "quotes"
    BARS = "bars"


class AssetType(Enum):
    """Type of asset being traded."""

    STOCK = "stock"
    CRYPTO = "crypto"


@dataclass
class TradingConfig:
    """
    Core trading API configuration.

    Attributes:
        api_key: Alpaca API key (loaded from env if not provided)
        api_secret: Alpaca API secret (loaded from env if not provided)
        base_url: Alpaca API base URL
        paper_mode: Use paper trading (default: True)
        dry_run: Simulate trades without API calls (default: False)
    """

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: str = "https://paper-api.alpaca.markets"
    paper_mode: bool = True
    dry_run: bool = False

    def __post_init__(self):
        """Load credentials from environment if not provided."""
        if self.api_key is None:
            self.api_key = os.getenv("ALPACA_API_KEY")
        if self.api_secret is None:
            self.api_secret = os.getenv("ALPACA_API_SECRET")
        if os.getenv("ALPACA_BASE_URL"):
            self.base_url = os.getenv("ALPACA_BASE_URL")

    def validate(self) -> tuple[bool, str]:
        """
        Validate configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.dry_run:
            # Dry run mode doesn't require credentials
            return True, ""
        if not self.api_key:
            return False, "ALPACA_API_KEY is required"
        if not self.api_secret:
            return False, "ALPACA_API_SECRET is required"
        return True, ""


@dataclass
class RiskConfig:
    """
    Risk management configuration for order validation.

    Attributes:
        max_position_size: Maximum position size per symbol (shares/coins)
        max_position_value: Maximum position value per symbol (dollars)
        max_total_exposure: Maximum total portfolio exposure
        max_orders_per_minute: Rate limit for orders per minute
        max_orders_per_symbol_per_minute: Rate limit per symbol per minute
        min_cash_buffer: Minimum cash to maintain
    """

    max_position_size: float = 1000.0
    max_position_value: float = 100_000.0
    max_total_exposure: float = 500_000.0
    max_orders_per_minute: int = 100
    max_orders_per_symbol_per_minute: int = 20
    min_cash_buffer: float = 1000.0


@dataclass
class StopLossConfig:
    """
    Stop-loss and circuit breaker configuration.

    Attributes:
        position_stop_pct: Per-position stop loss % from entry (e.g., 2.0 = 2%)
        trailing_stop_pct: Trailing stop % from peak price
        portfolio_stop_pct: Max portfolio loss % before circuit breaker
        max_drawdown_pct: Max drawdown % before circuit breaker
        use_trailing_stops: Enable trailing stops
        enable_circuit_breaker: Enable portfolio-level circuit breaker
    """

    position_stop_pct: float = 2.0
    trailing_stop_pct: float = 3.0
    portfolio_stop_pct: float = 5.0
    max_drawdown_pct: float = 10.0
    use_trailing_stops: bool = False
    enable_circuit_breaker: bool = True


@dataclass
class SymbolConfig:
    """
    Per-symbol configuration overrides.

    Attributes:
        symbol: Trading symbol
        asset_type: Asset type (stock or crypto)
        data_type: Market data type for this symbol
    """

    symbol: str
    asset_type: AssetType = AssetType.STOCK
    data_type: Optional[DataType] = None


@dataclass
class LiveEngineConfig:
    """
    Complete configuration for live trading engine.

    Combines all configuration components into a single object.

    Attributes:
        trading: Core trading API configuration
        risk: Risk management limits
        stop_loss: Stop-loss and circuit breaker settings
        enable_trading: Enable actual order submission
        enable_stop_loss: Enable stop-loss management
        log_orders: Enable order logging to CSV
        order_log_path: Path for order log CSV
        data_type: Default market data type
        symbols: Per-symbol configuration overrides
        status_log_interval: Ticks between status logs
    """

    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    stop_loss: StopLossConfig = field(default_factory=StopLossConfig)
    enable_trading: bool = True
    enable_stop_loss: bool = True
    close_positions_on_exit: bool = True  # Close all positions on Ctrl+C
    log_orders: bool = True
    order_log_path: str = "logs/live_orders.csv"
    data_type: DataType = DataType.TRADES
    symbols: list[SymbolConfig] = field(default_factory=list)
    status_log_interval: int = 100

    @classmethod
    def from_yaml(cls, path: str) -> "LiveEngineConfig":
        """
        Load configuration from a YAML file.

        Secrets (api_key, api_secret) are loaded from environment variables.

        Args:
            path: Path to YAML configuration file

        Returns:
            LiveEngineConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        # Parse nested configs
        trading_data = data.get("trading", {})
        trading_config = TradingConfig(
            # api_key and api_secret loaded from env via __post_init__
            base_url=trading_data.get("base_url", "https://paper-api.alpaca.markets"),
            paper_mode=trading_data.get("paper_mode", True),
            dry_run=trading_data.get("dry_run", False),
        )

        risk_data = data.get("risk", {})
        risk_config = RiskConfig(
            max_position_size=risk_data.get("max_position_size", 1000.0),
            max_position_value=risk_data.get("max_position_value", 100_000.0),
            max_total_exposure=risk_data.get("max_total_exposure", 500_000.0),
            max_orders_per_minute=risk_data.get("max_orders_per_minute", 100),
            max_orders_per_symbol_per_minute=risk_data.get(
                "max_orders_per_symbol_per_minute", 20
            ),
            min_cash_buffer=risk_data.get("min_cash_buffer", 1000.0),
        )

        stop_loss_data = data.get("stop_loss", {})
        stop_loss_config = StopLossConfig(
            position_stop_pct=stop_loss_data.get("position_stop_pct", 2.0),
            trailing_stop_pct=stop_loss_data.get("trailing_stop_pct", 3.0),
            portfolio_stop_pct=stop_loss_data.get("portfolio_stop_pct", 5.0),
            max_drawdown_pct=stop_loss_data.get("max_drawdown_pct", 10.0),
            use_trailing_stops=stop_loss_data.get("use_trailing_stops", False),
            enable_circuit_breaker=stop_loss_data.get("enable_circuit_breaker", True),
        )

        # Parse symbol configs
        symbols_data = data.get("symbols", [])
        symbol_configs = []
        for sym_data in symbols_data:
            if isinstance(sym_data, str):
                symbol_configs.append(SymbolConfig(symbol=sym_data))
            elif isinstance(sym_data, dict):
                asset_type_str = sym_data.get("asset_type", "stock").lower()
                asset_type = (
                    AssetType.CRYPTO if asset_type_str == "crypto" else AssetType.STOCK
                )
                data_type_str = sym_data.get("data_type")
                data_type = (
                    DataType(data_type_str.lower()) if data_type_str else None
                )
                symbol_configs.append(
                    SymbolConfig(
                        symbol=sym_data["symbol"],
                        asset_type=asset_type,
                        data_type=data_type,
                    )
                )

        # Parse data_type enum
        data_type_str = data.get("data_type", "trades").lower()
        data_type = DataType(data_type_str)

        return cls(
            trading=trading_config,
            risk=risk_config,
            stop_loss=stop_loss_config,
            enable_trading=data.get("enable_trading", True),
            enable_stop_loss=data.get("enable_stop_loss", True),
            close_positions_on_exit=data.get("close_positions_on_exit", True),
            log_orders=data.get("log_orders", True),
            order_log_path=data.get("order_log_path", "logs/live_orders.csv"),
            data_type=data_type,
            symbols=symbol_configs,
            status_log_interval=data.get("status_log_interval", 100),
        )

    @classmethod
    def from_env(cls) -> "LiveEngineConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            ALPACA_API_KEY: Alpaca API key (required unless dry_run)
            ALPACA_API_SECRET: Alpaca API secret (required unless dry_run)
            ALPACA_BASE_URL: Alpaca base URL
            TRADING_PAPER_MODE: Paper mode (true/false)
            TRADING_DRY_RUN: Dry run mode (true/false)
            TRADING_ENABLE: Enable trading (true/false)
            TRADING_DATA_TYPE: Data type (trades/quotes/bars)
            RISK_MAX_POSITION_SIZE: Max position size
            RISK_MAX_POSITION_VALUE: Max position value
            RISK_MAX_TOTAL_EXPOSURE: Max total exposure
            RISK_MAX_ORDERS_PER_MINUTE: Max orders per minute
            RISK_MIN_CASH_BUFFER: Min cash buffer
            STOPLOSS_POSITION_PCT: Position stop loss %
            STOPLOSS_TRAILING_PCT: Trailing stop %
            STOPLOSS_PORTFOLIO_PCT: Portfolio stop %
            STOPLOSS_MAX_DRAWDOWN_PCT: Max drawdown %
            STOPLOSS_USE_TRAILING: Use trailing stops (true/false)
            STOPLOSS_CIRCUIT_BREAKER: Enable circuit breaker (true/false)

        Returns:
            LiveEngineConfig instance
        """

        def get_bool(key: str, default: bool) -> bool:
            value = os.getenv(key)
            if value is None:
                return default
            return value.lower() in ("true", "1", "yes")

        def get_float(key: str, default: float) -> float:
            value = os.getenv(key)
            return float(value) if value else default

        def get_int(key: str, default: int) -> int:
            value = os.getenv(key)
            return int(value) if value else default

        trading_config = TradingConfig(
            paper_mode=get_bool("TRADING_PAPER_MODE", True),
            dry_run=get_bool("TRADING_DRY_RUN", False),
        )

        risk_config = RiskConfig(
            max_position_size=get_float("RISK_MAX_POSITION_SIZE", 1000.0),
            max_position_value=get_float("RISK_MAX_POSITION_VALUE", 100_000.0),
            max_total_exposure=get_float("RISK_MAX_TOTAL_EXPOSURE", 500_000.0),
            max_orders_per_minute=get_int("RISK_MAX_ORDERS_PER_MINUTE", 100),
            max_orders_per_symbol_per_minute=get_int(
                "RISK_MAX_ORDERS_PER_SYMBOL_PER_MINUTE", 20
            ),
            min_cash_buffer=get_float("RISK_MIN_CASH_BUFFER", 1000.0),
        )

        stop_loss_config = StopLossConfig(
            position_stop_pct=get_float("STOPLOSS_POSITION_PCT", 2.0),
            trailing_stop_pct=get_float("STOPLOSS_TRAILING_PCT", 3.0),
            portfolio_stop_pct=get_float("STOPLOSS_PORTFOLIO_PCT", 5.0),
            max_drawdown_pct=get_float("STOPLOSS_MAX_DRAWDOWN_PCT", 10.0),
            use_trailing_stops=get_bool("STOPLOSS_USE_TRAILING", False),
            enable_circuit_breaker=get_bool("STOPLOSS_CIRCUIT_BREAKER", True),
        )

        data_type_str = os.getenv("TRADING_DATA_TYPE", "trades").lower()
        data_type = DataType(data_type_str)

        return cls(
            trading=trading_config,
            risk=risk_config,
            stop_loss=stop_loss_config,
            enable_trading=get_bool("TRADING_ENABLE", True),
            enable_stop_loss=get_bool("TRADING_ENABLE_STOPLOSS", True),
            close_positions_on_exit=get_bool("TRADING_CLOSE_ON_EXIT", True),
            log_orders=get_bool("TRADING_LOG_ORDERS", True),
            order_log_path=os.getenv("TRADING_ORDER_LOG_PATH", "logs/live_orders.csv"),
            data_type=data_type,
            status_log_interval=get_int("TRADING_STATUS_INTERVAL", 100),
        )

    def validate(self) -> tuple[bool, str]:
        """
        Validate complete configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate trading config
        is_valid, error = self.trading.validate()
        if not is_valid:
            return False, error

        # Validate risk parameters
        if self.risk.max_position_size <= 0:
            return False, "max_position_size must be positive"
        if self.risk.max_position_value <= 0:
            return False, "max_position_value must be positive"
        if self.risk.max_total_exposure <= 0:
            return False, "max_total_exposure must be positive"
        if self.risk.max_orders_per_minute <= 0:
            return False, "max_orders_per_minute must be positive"
        if self.risk.min_cash_buffer < 0:
            return False, "min_cash_buffer must be non-negative"

        # Validate stop-loss parameters
        if self.stop_loss.position_stop_pct <= 0:
            return False, "position_stop_pct must be positive"
        if self.stop_loss.trailing_stop_pct <= 0:
            return False, "trailing_stop_pct must be positive"
        if self.stop_loss.portfolio_stop_pct <= 0:
            return False, "portfolio_stop_pct must be positive"
        if self.stop_loss.max_drawdown_pct <= 0:
            return False, "max_drawdown_pct must be positive"

        return True, ""

    def __repr__(self) -> str:
        mode = "DRY_RUN" if self.trading.dry_run else ("PAPER" if self.trading.paper_mode else "LIVE")
        return (
            f"LiveEngineConfig(mode={mode}, "
            f"trading={self.enable_trading}, "
            f"stop_loss={self.enable_stop_loss}, "
            f"data_type={self.data_type.value})"
        )
