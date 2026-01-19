#!/usr/bin/env python3
"""
Run Backtest

Entry point for running strategy backtests using Alpaca data.

Usage:
    python run_backtest.py                      # Run with defaults (AAPL, last year)
    python run_backtest.py --symbol MSFT        # Different symbol
    python run_backtest.py --start 2020-01-01   # Custom date range
    python run_backtest.py --capital 50000      # Custom initial capital
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.macd_strategy import MACDStrategy
from backtester.backtest_engine import BacktestEngine
from backtester.position_sizer import PercentSizer
from models import Timeframe

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_config(symbol: str, start, end, timeframe: str, capital: float, position_size: float, slippage: float) -> None:
    """Print backtest configuration."""
    print("\n" + "=" * 70)
    print("BACKTEST CONFIGURATION")
    print("=" * 70)
    print(f"  Symbol:         {symbol}")
    print(f"  Date range:     {start.date()} to {end.date()}")
    print(f"  Timeframe:      {timeframe}")
    print(f"  Initial capital: ${capital:,.2f}")
    print(f"  Position size:   {position_size * 100:.1f}%")
    print(f"  Slippage:        {slippage} bps")
    print("=" * 70 + "\n")


def print_results(results: dict, verbose: bool) -> None:
    """Print backtest results."""
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print(f"  Symbol:          {results['symbol']}")
    print(f"  Bars processed:  {results['bar_count']:,}")
    print(f"  Total trades:    {results['total_trades']}")
    print("-" * 70)
    print(f"  Initial capital: ${results['initial_capital']:,.2f}")
    print(f"  Final value:     ${results['final_value']:,.2f}")
    print(f"  Total return:    {results['total_return_pct']:.2f}%")
    print("=" * 70)

    if verbose and results['trades']:
        print("\nTRADE HISTORY:")
        print("-" * 70)
        for i, trade in enumerate(results['trades'][:10], 1):
            print(f"  {i}. {trade}")
        if len(results['trades']) > 10:
            print(f"  ... and {len(results['trades']) - 10} more trades")

    equity_curve = results['equity_curve']
    if equity_curve:
        values = [e['value'] for e in equity_curve]
        print("\nEQUITY CURVE:")
        print(f"  Peak:   ${max(values):,.2f}")
        print(f"  Trough: ${min(values):,.2f}")
        print(f"  Points: {len(equity_curve)}")


def main():
    parser = argparse.ArgumentParser(
        description="Run backtest using Alpaca data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--symbol",
        default="AAPL",
        help="Stock symbol to backtest (default: AAPL)",
    )
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=None,
        help="Start date YYYY-MM-DD (default: 1 year ago)",
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=None,
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--timeframe",
        choices=["1Day", "1Hour", "15Min", "5Min", "1Min"],
        default="1Day",
        help="Bar timeframe (default: 1Day)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial capital (default: 100000)",
    )
    parser.add_argument(
        "--position-size",
        type=float,
        default=0.10,
        help="Position size as fraction of equity (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.0,
        help="Slippage in basis points (default: 0)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment
    load_dotenv()

    # Set date range
    end = args.end or datetime.now()
    start = args.start or (end - timedelta(days=365))

    # Map timeframe
    timeframe_map = {
        "1Day": Timeframe.DAY_1,
        "1Hour": Timeframe.HOUR_1,
        "15Min": Timeframe.MIN_15,
        "5Min": Timeframe.MIN_5,
        "1Min": Timeframe.MIN_1,
    }
    timeframe = timeframe_map[args.timeframe]

    print_config(args.symbol, start, end, args.timeframe, args.capital, args.position_size, args.slippage)

    # Create gateway and connect
    gateway = AlpacaDataGateway()
    if not gateway.connect():
        logger.error("Failed to connect to Alpaca API")
        sys.exit(1)

    try:
        # Create strategy
        strategy = MACDStrategy(
            gateway=gateway,
            timeframe=timeframe,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        )

        # Create position sizer
        position_sizer = PercentSizer(equity_percent=args.position_size)

        # Create backtest engine
        engine = BacktestEngine(
            gateway=gateway,
            strategy=strategy,
            init_capital=args.capital,
            position_sizer=position_sizer,
            slippage_bps=args.slippage,
        )

        # Run backtest
        print("Running backtest...")
        results = engine.run(args.symbol, timeframe, start, end)

        print_results(results, args.verbose)

    finally:
        gateway.disconnect()


if __name__ == "__main__":
    main()
