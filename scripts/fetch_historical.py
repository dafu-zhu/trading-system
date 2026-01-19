#!/usr/bin/env python3
"""
Fetch Historical Data from Alpaca

Fetches historical bar data for configured symbols and stores in SQLite.
Supports resume capability and progress tracking.

Usage:
    python scripts/fetch_historical.py                  # Fetch all configured symbols
    python scripts/fetch_historical.py --symbols AAPL MSFT  # Fetch specific symbols
    python scripts/fetch_historical.py --start 2020-01-01   # Custom start date
    python scripts/fetch_historical.py --force              # Re-fetch all data
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gateway.alpaca_data_gateway import AlpacaDataGateway
from data_loader.storage import BarStorage
from models import Timeframe

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
DEFAULT_START = datetime(2017, 1, 1)
DEFAULT_END = datetime(2026, 1, 1)
DEFAULT_TIMEFRAME = Timeframe.DAY_1
CHUNK_DAYS = 365  # Fetch one year at a time


def fetch_symbol_data(
    gateway: AlpacaDataGateway,
    storage: BarStorage,
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    force: bool = False,
) -> int:
    """
    Fetch historical data for a single symbol.

    :param gateway: AlpacaDataGateway instance
    :param storage: BarStorage instance
    :param symbol: Stock symbol
    :param timeframe: Bar timeframe
    :param start: Start datetime
    :param end: End datetime
    :param force: If True, re-fetch all data
    :return: Number of bars fetched
    """
    # Check for existing data (resume capability)
    if not force:
        latest = storage.get_latest_timestamp(symbol, timeframe)
        if latest:
            # Start from the day after the latest data
            start = latest + timedelta(days=1)
            if start >= end:
                logger.info(
                    "%s: Data already up to date (latest: %s)",
                    symbol, latest.date()
                )
                return 0
            logger.info(
                "%s: Resuming from %s (latest: %s)",
                symbol, start.date(), latest.date()
            )

    total_bars = 0
    current_start = start

    while current_start < end:
        chunk_end = min(current_start + timedelta(days=CHUNK_DAYS), end)

        logger.info(
            "%s: Fetching %s to %s...",
            symbol, current_start.date(), chunk_end.date()
        )

        bars = gateway.fetch_bars(symbol, timeframe, current_start, chunk_end)
        total_bars += len(bars)

        current_start = chunk_end

    return total_bars


def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical data from Alpaca API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help=f"Symbols to fetch (default: {DEFAULT_SYMBOLS})",
    )
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=DEFAULT_START,
        help="Start date (YYYY-MM-DD, default: 2017-01-01)",
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=DEFAULT_END,
        help="End date (YYYY-MM-DD, default: 2026-01-01)",
    )
    parser.add_argument(
        "--timeframe",
        choices=["1Day", "1Hour", "15Min", "5Min", "1Min"],
        default="1Day",
        help="Bar timeframe (default: 1Day)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch all data (ignore existing)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show storage statistics and exit",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Map timeframe string to enum
    timeframe_map = {
        "1Day": Timeframe.DAY_1,
        "1Hour": Timeframe.HOUR_1,
        "15Min": Timeframe.MIN_15,
        "5Min": Timeframe.MIN_5,
        "1Min": Timeframe.MIN_1,
    }
    timeframe = timeframe_map[args.timeframe]

    # Initialize storage
    storage = BarStorage()

    # Show stats and exit if requested
    if args.stats:
        stats = storage.get_stats()
        print("\n" + "=" * 60)
        print("STORAGE STATISTICS")
        print("=" * 60)
        print(f"  Database: {stats['db_path']}")
        print(f"  Size: {stats['db_size_mb']:.2f} MB")
        print(f"  Total bars: {stats['total_bars']:,}")
        print(f"  Symbols: {stats['symbols']}")
        if stats['earliest']:
            print(f"  Date range: {stats['earliest']} to {stats['latest']}")
        print("=" * 60)

        # Per-symbol stats
        symbols = storage.get_symbols()
        if symbols:
            print("\nPer-symbol statistics:")
            for symbol in symbols:
                count = storage.get_bar_count(symbol, timeframe)
                earliest = storage.get_earliest_timestamp(symbol, timeframe)
                latest = storage.get_latest_timestamp(symbol, timeframe)
                if count > 0:
                    print(f"  {symbol}: {count:,} bars ({earliest.date()} to {latest.date()})")
        return

    # Initialize gateway
    gateway = AlpacaDataGateway(storage=storage)
    if not gateway.connect():
        logger.error("Failed to connect to Alpaca API")
        sys.exit(1)

    try:
        print("\n" + "=" * 60)
        print("FETCHING HISTORICAL DATA")
        print("=" * 60)
        print(f"  Symbols: {', '.join(args.symbols)}")
        print(f"  Date range: {args.start.date()} to {args.end.date()}")
        print(f"  Timeframe: {args.timeframe}")
        print(f"  Force re-fetch: {args.force}")
        print("=" * 60 + "\n")

        total_bars = 0
        results = {}

        for i, symbol in enumerate(args.symbols, 1):
            print(f"\n[{i}/{len(args.symbols)}] Processing {symbol}...")

            bars_fetched = fetch_symbol_data(
                gateway=gateway,
                storage=storage,
                symbol=symbol,
                timeframe=timeframe,
                start=args.start,
                end=args.end,
                force=args.force,
            )

            results[symbol] = bars_fetched
            total_bars += bars_fetched

        # Summary
        print("\n" + "=" * 60)
        print("FETCH COMPLETE")
        print("=" * 60)
        for symbol, count in results.items():
            status = f"{count:,} bars" if count > 0 else "up to date"
            print(f"  {symbol}: {status}")
        print(f"\n  Total new bars: {total_bars:,}")

        # Final storage stats
        stats = storage.get_stats()
        print(f"  Database size: {stats['db_size_mb']:.2f} MB")
        print("=" * 60)

    finally:
        gateway.disconnect()


if __name__ == "__main__":
    main()
