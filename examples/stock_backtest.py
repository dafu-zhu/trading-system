#!/usr/bin/env python3
"""
Stock Backtest Example - MACD Strategy on AAPL

Tests backtesting functionality with stock data.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

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
logger = logging.getLogger("stock_backtest")


def main():
    logger.info("=" * 60)
    logger.info("STOCK BACKTEST - MACD Strategy on AAPL")
    logger.info("=" * 60)

    # Configuration
    symbol = "AAPL"
    timeframe = Timeframe.DAY_1
    start = datetime.now() - timedelta(days=365)  # 1 year
    end = datetime.now() - timedelta(days=1)
    initial_capital = 100_000.0
    position_size_pct = 0.10

    logger.info(f"Symbol: {symbol}")
    logger.info(f"Timeframe: {timeframe.value}")
    logger.info(f"Period: {start.date()} to {end.date()}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info(f"Position Size: {position_size_pct * 100}%")
    logger.info("-" * 60)

    # Initialize components
    logger.info("Initializing data gateway...")
    data_gateway = AlpacaDataGateway()

    logger.info("Initializing MACD strategy...")
    strategy = MACDStrategy(
        symbols=[symbol],
        fast_period=12,
        slow_period=26,
        signal_period=9,
    )

    logger.info("Initializing position sizer...")
    position_sizer = PercentSizer(percent=position_size_pct)

    logger.info("Initializing backtest engine...")
    engine = BacktestEngine(
        data_gateway=data_gateway,
        strategy=strategy,
        initial_capital=initial_capital,
        position_sizer=position_sizer,
        slippage_bps=10,  # 10 basis points slippage
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
        logger.info(f"Total Trades: {results.get('total_trades', 0)}")
        logger.info(f"Winning Trades: {results.get('winning_trades', 0)}")
        logger.info(f"Losing Trades: {results.get('losing_trades', 0)}")

        win_rate = results.get('win_rate', 0)
        logger.info(f"Win Rate: {win_rate:.1f}%")

        total_pnl = results.get('total_pnl', 0)
        logger.info(f"Total P&L: ${total_pnl:,.2f}")

        final_equity = results.get('final_equity', initial_capital)
        logger.info(f"Final Equity: ${final_equity:,.2f}")

        total_return = ((final_equity - initial_capital) / initial_capital) * 100
        logger.info(f"Total Return: {total_return:.2f}%")

        max_drawdown = results.get('max_drawdown', 0)
        logger.info(f"Max Drawdown: {max_drawdown:.2f}%")
    else:
        logger.warning("No results returned from backtest")

    logger.info("=" * 60)
    logger.info("Stock backtest completed successfully!")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    main()
