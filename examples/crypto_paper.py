#!/usr/bin/env python3
"""
Crypto Paper Trading Example - Momentum Strategy on BTC/USD

Tests paper trading with real-time data simulation.
Crypto markets are 24/7, so this can run anytime.

Note: This uses paper trading mode - no real money involved.
"""

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from gateway.alpaca_data_gateway import AlpacaDataGateway
from gateway.alpaca_trading_gateway import AlpacaTradingGateway
from strategy.momentum_strategy import MomentumStrategy
from models import Timeframe, MarketSnapshot, OrderSide, OrderType

# Load environment variables from .env
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("crypto_paper")


class CryptoPaperEngine:
    """
    Paper trading engine for crypto.

    Uses Alpaca paper trading API for order execution.
    """

    def __init__(
        self,
        data_gateway,
        trading_gateway,
        strategy,
        symbol: str,
        position_size_pct: float = 0.10,
    ):
        self.data_gateway = data_gateway
        self.trading_gateway = trading_gateway
        self.strategy = strategy
        self.symbol = symbol
        self.position_size_pct = position_size_pct

        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.orders_submitted = 0

    def run(self, duration_minutes: int = 5, poll_interval: int = 30):
        """
        Run paper trading for specified duration.

        Args:
            duration_minutes: How long to run
            poll_interval: Seconds between price checks
        """
        logger.info(f"Starting paper trading for {duration_minutes} minutes...")
        logger.info(f"Poll interval: {poll_interval} seconds")
        logger.info("-" * 60)

        # Get account info
        account = self.trading_gateway.get_account()
        if account:
            logger.info(f"Account Equity: ${float(account.equity):,.2f}")
            logger.info(f"Buying Power: ${float(account.buying_power):,.2f}")
        else:
            logger.warning("Could not fetch account info")

        logger.info("-" * 60)

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        iteration = 0

        while datetime.now() < end_time:
            iteration += 1
            remaining = (end_time - datetime.now()).seconds

            logger.info(f"[Iteration {iteration}] {remaining}s remaining...")

            try:
                self._process_tick()
            except Exception as e:
                logger.error(f"Error processing tick: {e}")

            # Sleep between polls
            if datetime.now() < end_time:
                time.sleep(poll_interval)

        logger.info("-" * 60)
        logger.info("Paper trading session ended")
        logger.info(f"Orders submitted: {self.orders_submitted}")
        logger.info(f"Trades completed: {len(self.trades)}")

        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        logger.info(f"Session P&L: ${total_pnl:,.2f}")

        return {
            "orders": self.orders_submitted,
            "trades": len(self.trades),
            "pnl": total_pnl,
        }

    def _process_tick(self):
        """Process a single tick/price update."""
        # Get latest bar
        end = datetime.now()
        start = end - timedelta(hours=1)

        bars = self.data_gateway.fetch_bars(
            self.symbol,
            Timeframe.MIN_1,
            start,
            end
        )

        if not bars:
            logger.warning("No bars received")
            return

        latest_bar = bars[-1]
        current_price = latest_bar.close

        logger.info(f"  {self.symbol} @ ${current_price:,.2f}")

        # Create snapshot
        snapshot = MarketSnapshot(
            timestamp=latest_bar.timestamp,
            prices={self.symbol: current_price},
            bars={self.symbol: latest_bar},
        )

        # Generate signals
        signals = self.strategy.generate_signals(snapshot)

        for signal in signals:
            action = signal.get("action", "HOLD")

            if action == "HOLD":
                continue

            logger.info(f"  Signal: {action}")

            if action == "BUY" and self.position == 0:
                self._submit_buy(current_price)
            elif action == "SELL" and self.position > 0:
                self._submit_sell(current_price)

    def _submit_buy(self, price: float):
        """Submit a buy order via paper trading API."""
        # Calculate position size
        account = self.trading_gateway.get_account()
        if not account:
            logger.warning("Cannot get account for position sizing")
            return

        buying_power = float(account.buying_power)
        order_value = buying_power * self.position_size_pct
        qty = order_value / price

        if qty <= 0:
            logger.warning("Insufficient buying power")
            return

        logger.info(f"  Submitting BUY order: {qty:.6f} {self.symbol}")

        try:
            result = self.trading_gateway.submit_order(
                symbol=self.symbol,
                side=OrderSide.BUY,
                quantity=qty,
                order_type=OrderType.MARKET,
            )

            if result:
                self.orders_submitted += 1
                self.position = qty
                self.entry_price = price
                logger.info(f"  Order submitted: {result.order_id}")
            else:
                logger.warning("  Order submission failed")

        except Exception as e:
            logger.error(f"  Order error: {e}")

    def _submit_sell(self, price: float):
        """Submit a sell order via paper trading API."""
        if self.position <= 0:
            return

        logger.info(f"  Submitting SELL order: {self.position:.6f} {self.symbol}")

        try:
            result = self.trading_gateway.submit_order(
                symbol=self.symbol,
                side=OrderSide.SELL,
                quantity=self.position,
                order_type=OrderType.MARKET,
            )

            if result:
                self.orders_submitted += 1
                pnl = (price - self.entry_price) * self.position
                self.trades.append({
                    "entry": self.entry_price,
                    "exit": price,
                    "qty": self.position,
                    "pnl": pnl,
                })
                logger.info(f"  Order submitted: {result.order_id} | P&L: ${pnl:,.2f}")
                self.position = 0.0
                self.entry_price = 0.0
            else:
                logger.warning("  Order submission failed")

        except Exception as e:
            logger.error(f"  Order error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("CRYPTO PAPER TRADING - Momentum Strategy on BTC/USD")
    logger.info("=" * 60)
    logger.info("NOTE: This uses Alpaca PAPER trading - no real money!")
    logger.info("=" * 60)

    # Configuration
    symbol = "BTC/USD"
    duration_minutes = 2  # Short test duration
    poll_interval = 20  # Check every 20 seconds
    position_size_pct = 0.05  # 5% position size for safety

    logger.info(f"Symbol: {symbol}")
    logger.info(f"Duration: {duration_minutes} minutes")
    logger.info(f"Poll Interval: {poll_interval} seconds")
    logger.info(f"Position Size: {position_size_pct * 100}%")
    logger.info("-" * 60)

    # Initialize components
    logger.info("Initializing data gateway...")
    data_gateway = AlpacaDataGateway()
    data_gateway.connect()

    logger.info("Initializing trading gateway (PAPER mode)...")
    # Paper mode is default (uses paper-api.alpaca.markets)
    trading_gateway = AlpacaTradingGateway()
    trading_gateway.connect()

    logger.info("Initializing Momentum strategy...")
    strategy = MomentumStrategy(
        lookback=5,
        buy_threshold=0.003,  # 0.3% threshold for more signals
        sell_threshold=-0.003,
        cooldown_ticks=2,
    )

    logger.info("Initializing paper trading engine...")
    engine = CryptoPaperEngine(
        data_gateway=data_gateway,
        trading_gateway=trading_gateway,
        strategy=strategy,
        symbol=symbol,
        position_size_pct=position_size_pct,
    )

    # Run paper trading
    logger.info("-" * 60)
    logger.info("Starting paper trading session...")
    results = engine.run(
        duration_minutes=duration_minutes,
        poll_interval=poll_interval,
    )

    logger.info("=" * 60)
    logger.info("Crypto paper trading completed!")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    main()
