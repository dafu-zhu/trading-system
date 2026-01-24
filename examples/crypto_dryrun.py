#!/usr/bin/env python3
"""
Crypto Dry-Run Example - Momentum Strategy on BTC/USD

Tests dry-run mode with cryptocurrency data and momentum strategy.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.momentum_strategy import MomentumStrategy
from models import Timeframe, MarketSnapshot, MarketDataPoint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("crypto_dryrun")


class CryptoDryRunEngine:
    """Dry-run engine for crypto with momentum strategy."""

    def __init__(self, data_gateway, strategy, initial_capital=50_000):
        self.data_gateway = data_gateway
        self.strategy = strategy
        self.capital = initial_capital
        self.position = 0.0  # Fractional for crypto
        self.entry_price = 0.0
        self.trades = []

    def run(self, symbol: str, timeframe: Timeframe, days: int = 7):
        """Replay historical crypto data."""
        end = datetime.now()
        start = end - timedelta(days=days)

        logger.info(f"Fetching {days} days of {symbol} data...")
        bars = self.data_gateway.fetch_bars(symbol, timeframe, start, end)

        if not bars:
            logger.error("No bars fetched - check API credentials and symbol format")
            return None

        logger.info(f"Fetched {len(bars)} bars")
        logger.info(f"Price range: ${bars[0].close:,.2f} to ${bars[-1].close:,.2f}")
        logger.info("-" * 60)

        signals_generated = 0
        buys = 0
        sells = 0

        for i, bar in enumerate(bars):
            # Create snapshot for strategy
            snapshot = MarketSnapshot(
                timestamp=bar.timestamp,
                prices={symbol: bar.close},
                bars={symbol: bar},
            )

            # Generate signals
            signals = self.strategy.generate_signals(snapshot)

            for signal in signals:
                action = signal.get("action", "HOLD")
                if action == "HOLD":
                    continue

                signals_generated += 1

                if action == "BUY":
                    buys += 1
                    self._process_buy(signal, bar)
                elif action == "SELL":
                    sells += 1
                    self._process_sell(signal, bar)

            # Log progress every 100 bars
            if (i + 1) % 100 == 0:
                logger.info(
                    f"Processed {i + 1}/{len(bars)} bars | "
                    f"Signals: {signals_generated} (B:{buys} S:{sells})"
                )

        # Close any open position at end
        if self.position > 0:
            logger.info("Closing open position at end of replay...")
            self._force_close(bars[-1])

        logger.info("-" * 60)
        logger.info(f"Total signals: {signals_generated} (Buys: {buys}, Sells: {sells})")
        logger.info(f"Completed trades: {len(self.trades)}")

        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        logger.info(f"Total P&L: ${total_pnl:,.2f}")

        if self.trades:
            winning = [t for t in self.trades if t["pnl"] > 0]
            win_rate = len(winning) / len(self.trades) * 100
            logger.info(f"Win Rate: {win_rate:.1f}%")

        return {
            "signals": signals_generated,
            "trades": len(self.trades),
            "pnl": total_pnl,
            "buys": buys,
            "sells": sells,
        }

    def _process_buy(self, signal, bar):
        """Process buy signal."""
        if self.position > 0:
            return  # Already in position

        price = bar.close
        # Use 10% of capital
        amount = self.capital * 0.10 / price

        self.position = amount
        self.entry_price = price

        logger.info(
            f"[{bar.timestamp.strftime('%Y-%m-%d %H:%M')}] "
            f"BUY {amount:.6f} BTC @ ${price:,.2f}"
        )

    def _process_sell(self, signal, bar):
        """Process sell signal."""
        if self.position <= 0:
            return  # No position to sell

        price = bar.close
        pnl = (price - self.entry_price) * self.position

        logger.info(
            f"[{bar.timestamp.strftime('%Y-%m-%d %H:%M')}] "
            f"SELL {self.position:.6f} BTC @ ${price:,.2f} | P&L: ${pnl:,.2f}"
        )

        self.trades.append({
            "entry": self.entry_price,
            "exit": price,
            "amount": self.position,
            "pnl": pnl,
        })

        self.position = 0.0
        self.entry_price = 0.0

    def _force_close(self, bar):
        """Force close position at end."""
        if self.position > 0:
            price = bar.close
            pnl = (price - self.entry_price) * self.position
            self.trades.append({
                "entry": self.entry_price,
                "exit": price,
                "amount": self.position,
                "pnl": pnl,
            })
            logger.info(f"Force closed at ${price:,.2f} | P&L: ${pnl:,.2f}")
            self.position = 0.0


def main():
    logger.info("=" * 60)
    logger.info("CRYPTO DRY-RUN - Momentum Strategy on BTC/USD")
    logger.info("=" * 60)

    # Configuration
    symbol = "BTC/USD"
    timeframe = Timeframe.MIN_15  # 15-minute bars for momentum
    replay_days = 7  # 1 week
    initial_capital = 50_000.0

    logger.info(f"Symbol: {symbol}")
    logger.info(f"Timeframe: {timeframe.value}")
    logger.info(f"Replay Days: {replay_days}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info("-" * 60)

    # Initialize components
    logger.info("Initializing data gateway...")
    data_gateway = AlpacaDataGateway()
    data_gateway.connect()

    logger.info("Initializing Momentum strategy...")
    strategy = MomentumStrategy(
        lookback=10,
        buy_threshold=0.005,  # 0.5% momentum threshold
        sell_threshold=-0.005,
        cooldown_ticks=5,  # 5 bars cooldown between trades
    )

    logger.info("Initializing dry-run engine...")
    engine = CryptoDryRunEngine(
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
    logger.info("Crypto dry-run completed successfully!")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    main()
