"""
Simple momentum strategy for live trading testing.

Generates signals based on short-term price momentum.
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

from models import MarketDataPoint, MarketSnapshot, Strategy


@dataclass
class MomentumConfig:
    """Configuration for momentum strategy."""

    lookback: int = 5  # Number of ticks to look back
    buy_threshold: float = 0.001  # 0.1% price increase to trigger BUY
    sell_threshold: float = -0.001  # 0.1% price decrease to trigger SELL
    cooldown_ticks: int = 10  # Minimum ticks between signals


class MomentumStrategy(Strategy):
    """
    Simple momentum strategy for testing.

    Generates signals based on short-term price changes:
    - BUY: Price increased by threshold % over lookback period
    - SELL: Price decreased by threshold % over lookback period
    - HOLD: Price change within threshold

    This strategy triggers more frequently than MACD for testing purposes.
    """

    def __init__(
        self,
        lookback: int = 5,
        buy_threshold: float = 0.001,
        sell_threshold: float = -0.001,
        cooldown_ticks: int = 10,
    ):
        """
        Initialize momentum strategy.

        Args:
            lookback: Number of ticks to calculate momentum (default: 5)
            buy_threshold: Min price change % to trigger BUY (default: 0.1%)
            sell_threshold: Max price change % to trigger SELL (default: -0.1%)
            cooldown_ticks: Min ticks between signals (default: 10)
        """
        self.lookback = lookback
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.cooldown_ticks = cooldown_ticks

        # Price history per symbol
        self._price_history: dict[str, deque] = {}
        # Cooldown counter per symbol
        self._cooldown: dict[str, int] = {}
        # Last action per symbol (to alternate)
        self._last_action: dict[str, str] = {}

    def generate_signals(self, snapshot: MarketSnapshot) -> list:
        """
        Generate signals for all symbols in snapshot based on price momentum.

        Args:
            snapshot: Market snapshot with prices for all tracked symbols

        Returns:
            List of signal dicts for each symbol
        """
        signals = []
        for symbol, price in snapshot.prices.items():
            tick = MarketDataPoint(
                timestamp=snapshot.timestamp,
                symbol=symbol,
                price=price,
            )
            signal = self._generate_signal_for_tick(tick)
            signals.append(signal)
        return signals

    def _generate_signal_for_tick(self, tick: MarketDataPoint) -> dict:
        """
        Generate signal for a single tick based on price momentum.

        Args:
            tick: Market data point

        Returns:
            Signal dict
        """
        symbol = tick.symbol
        price = tick.price

        # Initialize history if needed
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=self.lookback + 1)
            self._cooldown[symbol] = 0
            self._last_action[symbol] = "SELL"  # Start ready to BUY

        history = self._price_history[symbol]
        history.append(price)

        # Decrement cooldown
        if self._cooldown[symbol] > 0:
            self._cooldown[symbol] -= 1

        # Need enough history
        if len(history) < self.lookback + 1:
            return self._make_signal("HOLD", tick, 0.0)

        # Calculate momentum (price change %)
        old_price = history[0]
        momentum = (price - old_price) / old_price if old_price > 0 else 0

        # Check cooldown
        if self._cooldown[symbol] > 0:
            return self._make_signal("HOLD", tick, momentum)

        # Generate signal based on momentum and last action
        action = "HOLD"

        if momentum >= self.buy_threshold and self._last_action[symbol] != "BUY":
            action = "BUY"
            self._last_action[symbol] = "BUY"
            self._cooldown[symbol] = self.cooldown_ticks
        elif momentum <= self.sell_threshold and self._last_action[symbol] != "SELL":
            action = "SELL"
            self._last_action[symbol] = "SELL"
            self._cooldown[symbol] = self.cooldown_ticks

        return self._make_signal(action, tick, momentum)

    @staticmethod
    def _make_signal(action: str, tick: MarketDataPoint, momentum: float) -> dict:
        """Create signal dict."""
        return {
            "action": action,
            "timestamp": tick.timestamp,
            "symbol": tick.symbol,
            "price": tick.price,
            "momentum": momentum,
        }

    def reset(self, symbol: Optional[str] = None) -> None:
        """Reset strategy state."""
        if symbol:
            self._price_history.pop(symbol, None)
            self._cooldown.pop(symbol, None)
            self._last_action.pop(symbol, None)
        else:
            self._price_history.clear()
            self._cooldown.clear()
            self._last_action.clear()
