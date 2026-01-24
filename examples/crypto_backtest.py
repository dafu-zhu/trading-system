#!/usr/bin/env python3
"""
Crypto Backtest Example - MACD Strategy on BTC/USD

Tests backtesting functionality with cryptocurrency data via Alpaca.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.macd_strategy import MACDStrategy
from backtester.backtest_engine import BacktestEngine
from backtester.position_sizer import PercentSizer
from models import Timeframe

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("crypto_backtest")


def main():
    logger.info("=" * 60)
    logger.info("CRYPTO BACKTEST - MACD Strategy on BTC/USD")
    logger.info("=" * 60)

    # Configuration - Crypto uses "/" format
    symbol = "BTC/USD"
    timeframe = Timeframe.HOUR_1  # Hourly for crypto (24/7 market)
    start = datetime.now() - timedelta(days=30)  # 30 days
    end = datetime.now() - timedelta(hours=1)
    initial_capital = 50_000.0
    position_size_pct = 0.10

    logger.info(f"Symbol: {symbol}")
    logger.info(f"Timeframe: {timeframe.value}")
    logger.info(f"Period: {start.date()} to {end.date()}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info(f"Position Size: {position_size_pct * 100}%")
    logger.info("-" * 60)

    # Initialize components
    logger.info("Initializing data gateway (Alpaca crypto)...")
    data_gateway = AlpacaDataGateway()
    data_gateway.connect()

    logger.info("Initializing MACD strategy...")
    strategy = MACDStrategy(
        gateway=data_gateway,
        timeframe=timeframe,
        fast_period=12,
        slow_period=26,
        signal_period=9,
    )

    logger.info("Initializing position sizer...")
    position_sizer = PercentSizer(equity_percent=position_size_pct)

    logger.info("Initializing backtest engine...")
    engine = BacktestEngine(
        gateway=data_gateway,
        strategy=strategy,
        init_capital=initial_capital,
        position_sizer=position_sizer,
        slippage_bps=20,  # Higher slippage for crypto
        max_volume_pct=1.0,  # Allow full volume for crypto (low liquidity data)
    )

    # Run backtest
    logger.info("-" * 60)
    logger.info("Running backtest...")
    results = engine.run(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
    )

    # Display results
    logger.info("-" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("-" * 60)

    if results:
        trades = results.get('trades', [])
        winning = [t for t in trades if t.get('pnl', 0) > 0]
        losing = [t for t in trades if t.get('pnl', 0) < 0]
        total_pnl = sum(t.get('pnl', 0) for t in trades)

        logger.info(f"Total Trades: {len(trades)}")
        logger.info(f"Winning Trades: {len(winning)}")
        logger.info(f"Losing Trades: {len(losing)}")

        win_rate = len(winning) / len(trades) * 100 if trades else 0
        logger.info(f"Win Rate: {win_rate:.1f}%")

        logger.info(f"Total P&L: ${total_pnl:,.2f}")

        final_equity = results.get('final_value', initial_capital)
        logger.info(f"Final Equity: ${final_equity:,.2f}")

        total_return = results.get('total_return_pct', 0)
        logger.info(f"Total Return: {total_return:.2f}%")
    else:
        logger.warning("No results returned from backtest")

    logger.info("=" * 60)
    logger.info("Crypto backtest completed successfully!")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    main()
