#!/usr/bin/env python3
"""
Alpha Strategy Backtest Example - Multi-Symbol Cross-Sectional

Tests the new alpha-based strategy with multiple symbols.
Uses equal-weighted alpha combination and cross-sectional ranking.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.alpha_strategy import AlphaStrategy, AlphaStrategyConfig
from data_loader.features.alpha_loader import AlphaLoader, AlphaLoaderConfig
from backtester.backtest_engine import BacktestEngine
from backtester.position_sizer import PercentSizer
from models import Timeframe, MarketSnapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("alpha_backtest")


class AlphaBacktestEngine:
    """
    Backtest engine for multi-symbol alpha strategies.

    Uses run_multi() for simultaneous symbol processing.
    """

    def __init__(
        self,
        data_gateway,
        strategy,
        initial_capital: float = 100_000,
        position_size_pct: float = 0.10,
    ):
        self.data_gateway = data_gateway
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position_size_pct = position_size_pct

        self.positions: dict[str, float] = {}  # symbol -> shares
        self.entry_prices: dict[str, float] = {}
        self.trades = []

    def run(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> dict:
        """Run multi-symbol backtest."""
        logger.info(f"Fetching data for {len(symbols)} symbols...")

        # Fetch bars for all symbols
        all_bars: dict[str, list] = {}
        for symbol in symbols:
            bars = self.data_gateway.fetch_bars(symbol, timeframe, start, end)
            if bars:
                all_bars[symbol] = bars
                logger.info(f"  {symbol}: {len(bars)} bars")
            else:
                logger.warning(f"  {symbol}: No data")

        if not all_bars:
            logger.error("No data fetched for any symbol")
            return None

        # Get all unique timestamps
        all_timestamps = set()
        for bars in all_bars.values():
            for bar in bars:
                all_timestamps.add(bar.timestamp)

        timestamps = sorted(all_timestamps)
        logger.info(f"Processing {len(timestamps)} time periods...")
        logger.info("-" * 60)

        # Build bar lookup
        bar_lookup: dict[str, dict] = {s: {} for s in symbols}
        for symbol, bars in all_bars.items():
            for bar in bars:
                bar_lookup[symbol][bar.timestamp] = bar

        # Process each timestamp
        signals_count = 0
        for i, ts in enumerate(timestamps):
            # Build snapshot
            prices = {}
            bars = {}
            for symbol in symbols:
                if ts in bar_lookup[symbol]:
                    bar = bar_lookup[symbol][ts]
                    prices[symbol] = bar.close
                    bars[symbol] = bar

            if not prices:
                continue

            snapshot = MarketSnapshot(
                timestamp=ts,
                prices=prices,
                bars=bars,
            )

            # Generate signals
            signals = self.strategy.generate_signals(snapshot)

            for signal in signals:
                action = signal.get("action", "HOLD")
                symbol = signal.get("symbol")

                if action == "HOLD" or not symbol:
                    continue

                signals_count += 1
                self._process_signal(signal, snapshot)

            # Log progress
            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(timestamps)} periods...")

        # Close all open positions
        logger.info("-" * 60)
        logger.info("Closing open positions...")
        self._close_all_positions(timestamps[-1], bar_lookup)

        # Calculate results
        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        final_equity = self.initial_capital + total_pnl

        winning = [t for t in self.trades if t["pnl"] > 0]
        win_rate = len(winning) / len(self.trades) * 100 if self.trades else 0

        logger.info("-" * 60)
        logger.info("RESULTS")
        logger.info(f"  Signals Generated: {signals_count}")
        logger.info(f"  Total Trades: {len(self.trades)}")
        logger.info(f"  Win Rate: {win_rate:.1f}%")
        logger.info(f"  Total P&L: ${total_pnl:,.2f}")
        logger.info(f"  Final Equity: ${final_equity:,.2f}")
        logger.info(
            f"  Return: {((final_equity - self.initial_capital) / self.initial_capital) * 100:.2f}%"
        )

        return {
            "signals": signals_count,
            "trades": len(self.trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "final_equity": final_equity,
        }

    def _process_signal(self, signal, snapshot):
        """Process a trading signal."""
        action = signal["action"]
        symbol = signal["symbol"]
        price = snapshot.prices.get(symbol, 0)

        if action == "BUY" and symbol not in self.positions:
            # Calculate position size
            position_value = self.capital * self.position_size_pct
            shares = int(position_value / price) if price > 0 else 0

            if shares > 0:
                self.positions[symbol] = shares
                self.entry_prices[symbol] = price
                logger.info(
                    f"[{snapshot.timestamp.strftime('%Y-%m-%d')}] "
                    f"BUY {shares} {symbol} @ ${price:.2f}"
                )

        elif action == "SELL" and symbol in self.positions:
            shares = self.positions[symbol]
            entry = self.entry_prices[symbol]
            pnl = (price - entry) * shares

            logger.info(
                f"[{snapshot.timestamp.strftime('%Y-%m-%d')}] "
                f"SELL {shares} {symbol} @ ${price:.2f} | P&L: ${pnl:.2f}"
            )

            self.trades.append({
                "symbol": symbol,
                "entry": entry,
                "exit": price,
                "shares": shares,
                "pnl": pnl,
            })

            del self.positions[symbol]
            del self.entry_prices[symbol]

    def _close_all_positions(self, last_ts, bar_lookup):
        """Close all remaining positions."""
        for symbol in list(self.positions.keys()):
            if last_ts in bar_lookup[symbol]:
                price = bar_lookup[symbol][last_ts].close
                shares = self.positions[symbol]
                entry = self.entry_prices[symbol]
                pnl = (price - entry) * shares

                logger.info(f"  Closing {symbol}: {shares} @ ${price:.2f} | P&L: ${pnl:.2f}")

                self.trades.append({
                    "symbol": symbol,
                    "entry": entry,
                    "exit": price,
                    "shares": shares,
                    "pnl": pnl,
                })

                del self.positions[symbol]
                del self.entry_prices[symbol]


def main():
    logger.info("=" * 60)
    logger.info("ALPHA BACKTEST - Multi-Symbol Cross-Sectional Strategy")
    logger.info("=" * 60)

    # Configuration
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    timeframe = Timeframe.DAY_1
    start = datetime.now() - timedelta(days=180)  # 6 months
    end = datetime.now() - timedelta(days=1)
    initial_capital = 100_000.0

    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Timeframe: {timeframe.value}")
    logger.info(f"Period: {start.date()} to {end.date()}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info("-" * 60)

    # Initialize components
    logger.info("Initializing data gateway...")
    data_gateway = AlpacaDataGateway()
    data_gateway.connect()

    logger.info("Initializing alpha loader...")
    alpha_loader = AlphaLoader(AlphaLoaderConfig(
        cache_ttl_minutes=60,
        lookback_days=252,
    ))

    logger.info("Initializing alpha strategy...")
    config = AlphaStrategyConfig(
        alpha_names=["momentum_20d", "mean_reversion"],
        long_threshold=0.3,
        short_threshold=-0.3,
        max_positions=2,
        refresh_frequency="daily",
    )
    strategy = AlphaStrategy(
        symbols=symbols,
        config=config,
        alpha_loader=alpha_loader,
    )

    logger.info("Alpha config:")
    logger.info(f"  Alphas: {config.alpha_names}")
    logger.info(f"  Long Threshold: {config.long_threshold}")
    logger.info(f"  Short Threshold: {config.short_threshold}")
    logger.info(f"  Max Positions: {config.max_positions}")

    logger.info("Initializing backtest engine...")
    engine = AlphaBacktestEngine(
        data_gateway=data_gateway,
        strategy=strategy,
        initial_capital=initial_capital,
        position_size_pct=0.20,  # 20% per position
    )

    # Run backtest
    logger.info("-" * 60)
    logger.info("Running multi-symbol backtest...")
    results = engine.run(
        symbols=symbols,
        timeframe=timeframe,
        start=start,
        end=end,
    )

    logger.info("=" * 60)
    logger.info("Alpha backtest completed!")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    main()
