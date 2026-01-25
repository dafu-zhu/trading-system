#!/usr/bin/env python3
"""
Run All Trading System Tests

Executes all example scripts and reports results.
Use this to verify the system is working correctly.
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_runner")

# Disable verbose logging from sub-modules during test run
logging.getLogger("alpaca").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def run_test(name: str, test_func) -> dict:
    """Run a single test and capture results."""
    logger.info(f"\n{'='*60}")
    logger.info(f"RUNNING: {name}")
    logger.info("=" * 60)

    start_time = datetime.now()
    try:
        result = test_func()
        elapsed = (datetime.now() - start_time).total_seconds()
        return {
            "name": name,
            "status": "PASS",
            "elapsed": elapsed,
            "result": result,
            "error": None,
        }
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"Test failed: {e}")
        traceback.print_exc()
        return {
            "name": name,
            "status": "FAIL",
            "elapsed": elapsed,
            "result": None,
            "error": str(e),
        }


def main():
    """Run all tests and report results."""
    logger.info("=" * 60)
    logger.info("TRADING SYSTEM TEST SUITE")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Import test modules
    sys.path.insert(0, str(Path(__file__).parent))

    results = []

    # Test 1: Stock Backtest
    from stock_backtest import main as stock_backtest_main
    results.append(run_test("Stock Backtest (MACD/AAPL)", stock_backtest_main))

    # Test 2: Stock Dry-Run
    from stock_dryrun import main as stock_dryrun_main
    results.append(run_test("Stock Dry-Run (MACD/AAPL)", stock_dryrun_main))

    # Test 3: Crypto Backtest
    from crypto_backtest import main as crypto_backtest_main
    results.append(run_test("Crypto Backtest (MACD/BTC)", crypto_backtest_main))

    # Test 4: Crypto Dry-Run
    from crypto_dryrun import main as crypto_dryrun_main
    results.append(run_test("Crypto Dry-Run (Momentum/BTC)", crypto_dryrun_main))

    # Test 5: Alpha Backtest
    from alpha_backtest import main as alpha_backtest_main
    results.append(run_test("Alpha Backtest (Multi-Symbol)", alpha_backtest_main))

    # Note: Crypto Paper Trading is optional (requires API interaction)
    # Uncomment to include:
    # from crypto_paper import main as crypto_paper_main
    # results.append(run_test("Crypto Paper (Momentum/BTC)", crypto_paper_main))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    for r in results:
        status_icon = "✓" if r["status"] == "PASS" else "✗"
        logger.info(f"  {status_icon} {r['name']}: {r['status']} ({r['elapsed']:.1f}s)")
        if r["error"]:
            logger.info(f"      Error: {r['error'][:50]}...")

    logger.info("-" * 60)
    logger.info(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    results = main()
    # Exit with error code if any tests failed
    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(failed)
