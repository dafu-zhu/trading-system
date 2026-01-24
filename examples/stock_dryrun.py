#!/usr/bin/env python3
"""
Stock Dry-Run Example - MACD Strategy on AAPL

Tests dry-run mode: replays historical data without API calls.
"""

import logging
import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.macd_strategy import MACDStrategy
from models import Timeframe, MarketSnapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("stock_dryrun")


class DryRunEngine:
    """Simple dry-run engine that replays historical data."""

    def __init__(self, data_gateway, strategy, initial_capital=100_000):
        self.data_gateway = data_gateway
        self.strategy = strategy
        self.capital = initial_capital
        self.position = 0
        self.entry_price = 0.0
        self.trades = []

    def run(self, symbol: str, timeframe: Timeframe, days: int = 30):
        """Replay historical data and generate signals."""
        end = datetime.now()
        start = end - timedelta(days=days)

        logger.info(f"Fetching {days} days of historical data...")
        bars = self.data_gateway.fetch_bars(symbol, timeframe, start, end)

        if not bars:
            logger.error("No bars fetched")
            return None

        logger.info(f"Fetched {len(bars)} bars")
        logger.info("-" * 60)

        signals_generated = 0
        for i, bar in enumerate(bars):
            # Create snapshot
            snapshot = MarketSnapshot(
                timestamp=bar.timestamp,
                prices={symbol: bar.close},
                bars={symbol: bar},
            )

            # Generate signals
            signals = self.strategy.generate_signals(snapshot)

            for signal in signals:
                if signal["action"] == "HOLD":
                    continue

                signals_generated += 1
                self._process_signal(signal, bar)

            # Log progress every 50 bars
            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(bars)} bars...")

        logger.info("-" * 60)
        logger.info(f"Total signals generated: {signals_generated}")
        logger.info(f"Total trades executed: {len(self.trades)}")

        # Calculate final P&L
        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        logger.info(f"Total P&L: ${total_pnl:,.2f}")

        return {
            "signals": signals_generated,
            "trades": len(self.trades),
            "pnl": total_pnl,
        }

    def _process_signal(self, signal, bar):
        """Process a trading signal (simulated)."""
        action = signal["action"]
        symbol = signal["symbol"]
        price = bar.close

        if action == "BUY" and self.position == 0:
            shares = int(self.capital * 0.1 / price)  # 10% position
            if shares > 0:
                self.position = shares
                self.entry_price = price
                logger.info(
                    f"[{bar.timestamp.strftime('%Y-%m-%d')}] BUY {shares} {symbol} @ ${price:.2f}"
                )

        elif action == "SELL" and self.position > 0:
            pnl = (price - self.entry_price) * self.position
            logger.info(
                f"[{bar.timestamp.strftime('%Y-%m-%d')}] SELL {self.position} {symbol} @ ${price:.2f} | P&L: ${pnl:.2f}"
            )
            self.trades.append({
                "symbol": symbol,
                "entry": self.entry_price,
                "exit": price,
                "shares": self.position,
                "pnl": pnl,
            })
            self.position = 0
            self.entry_price = 0.0


def main():
    logger.info("=" * 60)
    logger.info("STOCK DRY-RUN - MACD Strategy on AAPL")
    logger.info("=" * 60)

    # Configuration
    symbol = "AAPL"
    timeframe = Timeframe.DAY_1
    replay_days = 90  # 3 months
    initial_capital = 100_000.0

    logger.info(f"Symbol: {symbol}")
    logger.info(f"Timeframe: {timeframe.value}")
    logger.info(f"Replay Days: {replay_days}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info("-" * 60)

    # Initialize components
    logger.info("Initializing data gateway...")
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

    logger.info("Initializing dry-run engine...")
    engine = DryRunEngine(
        data_gateway=data_gateway,
        strategy=strategy,
        initial_capital=initial_capital,
    )

    # Run dry-run
    logger.info("-" * 60)
    logger.info("Starting historical replay (DRY-RUN mode)...")
    results = engine.run(
        symbol=symbol,
        timeframe=timeframe,
        days=replay_days,
    )

    logger.info("=" * 60)
    logger.info("Stock dry-run completed successfully!")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    main()
