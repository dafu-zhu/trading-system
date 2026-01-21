#!/usr/bin/env python
"""
Live Trading CLI - Entry point for running live trading sessions.

Usage:
    python run_live.py --symbols AAPL MSFT --dry-run
    python run_live.py --symbols AAPL --config config/live_trading.yaml
    python run_live.py --symbols BTC/USD ETH/USD --data-type trades
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from config.trading_config import LiveEngineConfig, DataType
from live.live_engine import LiveTradingEngine
from models import Timeframe

# Strategy imports
from strategy.macd_strategy import MACDStrategy
from gateway.alpaca_data_gateway import AlpacaDataGateway

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130


def setup_logging(log_level: str, log_file: str = "logs/live_trading.log") -> None:
    """
    Configure logging with file and console handlers.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
    """
    # Create logs directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Root logger config
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)


def get_strategy(name: str, data_gateway, timeframe: Timeframe = Timeframe.MIN_1):
    """
    Get strategy instance by name.

    Args:
        name: Strategy class name
        data_gateway: Data gateway for strategy
        timeframe: Timeframe for strategy

    Returns:
        Strategy instance
    """
    strategies = {
        "MACDStrategy": MACDStrategy,
    }

    if name not in strategies:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(strategies.keys())}")

    return strategies[name](data_gateway, timeframe)


def validate_credentials(config: LiveEngineConfig) -> bool:
    """
    Validate Alpaca credentials.

    Args:
        config: Live engine configuration

    Returns:
        True if credentials are valid
    """
    if config.trading.dry_run:
        return True

    api_key = config.trading.api_key
    api_secret = config.trading.api_secret

    if not api_key or not api_secret:
        logging.error("Alpaca credentials not found. Set ALPACA_API_KEY and ALPACA_API_SECRET.")
        return False

    if api_key.startswith("<") or api_secret.startswith("<"):
        logging.error("Alpaca credentials appear to be placeholders. Set actual values.")
        return False

    return True


def print_banner(config: LiveEngineConfig, symbols: list[str], strategy_name: str) -> None:
    """Print startup banner."""
    mode = "DRY_RUN" if config.trading.dry_run else (
        "PAPER" if config.trading.paper_mode else "LIVE"
    )

    print("\n" + "=" * 60)
    print(" LIVE TRADING SYSTEM ".center(60, "="))
    print("=" * 60)
    print(f" Mode:       {mode}")
    print(f" Trading:    {'ENABLED' if config.enable_trading else 'DISABLED'}")
    print(f" Stop-Loss:  {'ENABLED' if config.enable_stop_loss else 'DISABLED'}")
    print(f" Strategy:   {strategy_name}")
    print(f" Data Type:  {config.data_type.value}")
    print(f" Symbols:    {', '.join(symbols)}")
    print(f" Log Orders: {'YES' if config.log_orders else 'NO'}")
    print("=" * 60 + "\n")


def confirm_live_trading() -> bool:
    """
    Prompt for confirmation before live trading.

    Returns:
        True if user confirms
    """
    print("\n" + "!" * 60)
    print(" WARNING: LIVE TRADING MODE ".center(60, "!"))
    print("!" * 60)
    print("\nThis will execute REAL orders with REAL money.")
    print("Are you sure you want to continue?\n")

    try:
        response = input("Type 'YES' to confirm: ")
        return response.strip() == "YES"
    except (EOFError, KeyboardInterrupt):
        return False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run live trading with the specified strategy and symbols.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (no real orders)
  python run_live.py --symbols AAPL MSFT --dry-run

  # Paper trading
  python run_live.py --symbols AAPL --paper

  # With custom config
  python run_live.py --symbols AAPL --config config/my_config.yaml

  # Crypto trading
  python run_live.py --symbols BTC/USD ETH/USD --data-type trades

  # Historical replay (dry run)
  python run_live.py --symbols AAPL --dry-run --replay-days 7
        """,
    )

    # Required
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Space-separated list of symbols to trade (e.g., AAPL MSFT)",
    )

    # Config
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config YAML file (default: config/live_trading.yaml)",
    )

    # Trading mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no real orders)",
    )
    mode_group.add_argument(
        "--paper",
        action="store_true",
        help="Paper trading mode (Alpaca paper account)",
    )
    mode_group.add_argument(
        "--live",
        action="store_true",
        help="Live trading mode (real orders)",
    )

    # Strategy
    parser.add_argument(
        "--strategy",
        type=str,
        default="MACDStrategy",
        help="Strategy class name (default: MACDStrategy)",
    )

    # Data type
    parser.add_argument(
        "--data-type",
        type=str,
        choices=["trades", "quotes", "bars"],
        default="trades",
        help="Market data type (default: trades)",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    # Replay mode (for dry run)
    parser.add_argument(
        "--replay-days",
        type=int,
        default=None,
        help="For dry-run: replay historical data from N days ago",
    )

    parser.add_argument(
        "--timeframe",
        type=str,
        choices=["1Min", "5Min", "15Min", "1Hour", "1Day"],
        default="1Min",
        help="Timeframe for historical replay (default: 1Min)",
    )

    # Skip confirmation
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt for live trading",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    # Load environment variables from .env file
    load_dotenv()

    args = parse_args()

    # Setup logging first
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Load config
        config_path = args.config
        if config_path and Path(config_path).exists():
            config = LiveEngineConfig.from_yaml(config_path)
            logger.info("Loaded config from %s", config_path)
        else:
            # Try default paths
            default_paths = [
                "config/live_trading.yaml",
                os.environ.get("TRADING_CONFIG_PATH", ""),
            ]
            config = None
            for path in default_paths:
                if path and Path(path).exists():
                    config = LiveEngineConfig.from_yaml(path)
                    logger.info("Loaded config from %s", path)
                    break

            if config is None:
                logger.info("No config file found, using environment variables")
                config = LiveEngineConfig.from_env()

        # Override with CLI arguments
        if args.dry_run:
            config.trading.dry_run = True
            config.trading.paper_mode = True
            config.enable_trading = False
        elif args.paper:
            config.trading.dry_run = False
            config.trading.paper_mode = True
            config.enable_trading = True
        elif args.live:
            config.trading.dry_run = False
            config.trading.paper_mode = False
            config.enable_trading = True

        # Set data type
        config.data_type = DataType(args.data_type)

        # Validate credentials
        if not validate_credentials(config):
            return EXIT_ERROR

        # Print banner
        print_banner(config, args.symbols, args.strategy)

        # Confirm live trading
        if not config.trading.paper_mode and not config.trading.dry_run and not args.yes:
            if not confirm_live_trading():
                logger.info("Live trading cancelled by user")
                return EXIT_SUCCESS

        # Create data gateway for strategy
        data_gateway = AlpacaDataGateway(
            api_key=config.trading.api_key,
            api_secret=config.trading.api_secret,
        )
        if not data_gateway.connect():
            logger.error("Failed to connect to data gateway")
            return EXIT_ERROR

        # Create strategy
        timeframe_map = {
            "1Min": Timeframe.MIN_1,
            "5Min": Timeframe.MIN_5,
            "15Min": Timeframe.MIN_15,
            "1Hour": Timeframe.HOUR_1,
            "1Day": Timeframe.DAY_1,
        }
        timeframe = timeframe_map.get(args.timeframe, Timeframe.MIN_1)
        strategy = get_strategy(args.strategy, data_gateway, timeframe)

        # Create engine
        engine = LiveTradingEngine(
            config=config,
            strategy=strategy,
            data_gateway=data_gateway,
        )

        # Run engine
        logger.info("Starting live trading engine...")

        if args.dry_run and args.replay_days:
            # Historical replay mode
            end = datetime.now()
            start = end - timedelta(days=args.replay_days)
            engine.run(
                symbols=args.symbols,
                replay_start=start,
                replay_end=end,
                replay_timeframe=timeframe,
            )
        else:
            # Real-time streaming
            engine.run(symbols=args.symbols)

        return EXIT_SUCCESS

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return EXIT_INTERRUPTED

    except Exception as e:
        logger.exception("Fatal error: %s", e)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
