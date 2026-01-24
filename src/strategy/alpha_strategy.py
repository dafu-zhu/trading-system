"""
Alpha-based trading strategy.

Generates signals based on cross-sectional alpha rankings.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

from data_loader.features.alpha_loader import AlphaLoader, AlphaLoaderConfig
from models import MarketSnapshot, Strategy
from strategy.alpha_weights import (
    AlphaWeightModel,
    EqualWeightModel,
    WeightResult,
)

logger = logging.getLogger(__name__)


@dataclass
class AlphaStrategyConfig:
    """Configuration for AlphaStrategy."""

    alpha_names: list[str] = field(default_factory=lambda: ["momentum_20d"])
    long_threshold: float = 0.5
    short_threshold: float = -0.5
    refresh_frequency: str = "daily"  # "daily" or "hourly"
    max_positions: int = 10


class AlphaStrategy(Strategy):
    """
    Multi-symbol alpha-based strategy.

    Generates BUY/SELL signals based on cross-sectional alpha rankings:
    - Top N symbols (above long_threshold) -> BUY
    - Bottom N symbols (below short_threshold) -> SELL
    - Rest -> HOLD

    Uses equal weighting for alphas by default. Custom weight models can be
    provided for more sophisticated weighting schemes.

    Example:
        config = AlphaStrategyConfig(
            alpha_names=["momentum_20d", "mean_reversion"],
            long_threshold=0.5,
            max_positions=10,
        )
        strategy = AlphaStrategy(["AAPL", "MSFT"], config)
    """

    def __init__(
        self,
        symbols: list[str],
        config: Optional[AlphaStrategyConfig] = None,
        alpha_loader: Optional[AlphaLoader] = None,
        weight_model: Optional[AlphaWeightModel] = None,
    ):
        """
        Initialize alpha strategy.

        Args:
            symbols: List of symbols to trade
            config: Strategy configuration
            alpha_loader: Alpha data loader
            weight_model: Model for computing alpha weights. Defaults to EqualWeightModel.
        """
        self.symbols = symbols
        self.config = config or AlphaStrategyConfig()
        self.alpha_loader = alpha_loader or AlphaLoader(AlphaLoaderConfig())
        self.weight_model = weight_model or EqualWeightModel()

        # State management
        self._combined_alpha: dict[str, float] = {}
        self._current_signals: dict[str, str] = {}
        self._last_refresh: Optional[datetime] = None
        self._rankings: list[tuple[str, float]] = []
        self._current_weights: Optional[WeightResult] = None

    def generate_signals(self, snapshot: MarketSnapshot) -> list:
        """
        Generate signals for all symbols in snapshot.

        Args:
            snapshot: Market snapshot with prices for tracked symbols

        Returns:
            List of signal dicts for each symbol
        """
        if self._needs_refresh(snapshot.timestamp):
            self._refresh_alphas(snapshot.timestamp)

        signals = []
        for symbol in snapshot.prices.keys():
            if symbol not in self.symbols:
                continue

            signal = self._generate_signal_for_symbol(symbol, snapshot)
            signals.append(signal)

        return signals

    def _needs_refresh(self, timestamp: datetime) -> bool:
        """Check if alpha data needs refresh."""
        if self._last_refresh is None:
            return True

        if self.config.refresh_frequency == "daily":
            return timestamp.date() != self._last_refresh.date()
        elif self.config.refresh_frequency == "hourly":
            elapsed = timestamp - self._last_refresh
            return elapsed >= timedelta(hours=1)
        else:
            return False

    def _refresh_alphas(self, timestamp: datetime) -> None:
        """Refresh alpha data and compute combined alphas."""
        logger.info(f"Refreshing alphas at {timestamp}")

        # Compute weights using weight model
        self._current_weights = self.weight_model.compute_weights(
            self.config.alpha_names
        )
        logger.debug(
            f"Using weights from {self.weight_model.name}: {self._current_weights.weights}"
        )

        # Load and combine alphas
        combined: dict[str, float] = {symbol: 0.0 for symbol in self.symbols}

        for alpha_name in self.config.alpha_names:
            weight = self._current_weights.get_weight(alpha_name)
            alpha_values = self.alpha_loader.get_alpha_for_date(
                alpha_name, self.symbols, timestamp
            )

            for symbol, value in alpha_values.items():
                if symbol in combined:
                    combined[symbol] += value * weight

        self._combined_alpha = combined

        # Compute rankings
        self._rankings = sorted(
            combined.items(), key=lambda x: x[1], reverse=True
        )

        self._compute_signals()
        self._last_refresh = timestamp

    def _compute_signals(self) -> None:
        """Compute signals from rankings."""
        n_symbols = len(self._rankings)
        if n_symbols == 0:
            return

        max_long = min(self.config.max_positions, n_symbols)
        max_short = min(self.config.max_positions, n_symbols)

        for i, (symbol, alpha_value) in enumerate(self._rankings):
            if i < max_long and alpha_value >= self.config.long_threshold:
                self._current_signals[symbol] = "BUY"
            elif (
                i >= n_symbols - max_short
                and alpha_value <= self.config.short_threshold
            ):
                self._current_signals[symbol] = "SELL"
            else:
                self._current_signals[symbol] = "HOLD"

    def _generate_signal_for_symbol(
        self, symbol: str, snapshot: MarketSnapshot
    ) -> dict:
        """Generate signal dict for a single symbol."""
        action = self._current_signals.get(symbol, "HOLD")
        price = snapshot.prices.get(symbol, 0.0)
        alpha_value = self._combined_alpha.get(symbol, 0.0)

        return {
            "action": action,
            "timestamp": snapshot.timestamp,
            "symbol": symbol,
            "price": price,
            "alpha": alpha_value,
        }

    def generate_signals_batch(self, timestamp: datetime) -> dict[str, dict]:
        """
        Generate signals for all symbols at once.

        Args:
            timestamp: Current timestamp

        Returns:
            Dictionary mapping symbol -> signal dict
        """
        if self._needs_refresh(timestamp):
            self._refresh_alphas(timestamp)

        result = {}
        for symbol in self.symbols:
            action = self._current_signals.get(symbol, "HOLD")
            alpha_value = self._combined_alpha.get(symbol, 0.0)
            result[symbol] = {
                "action": action,
                "timestamp": timestamp,
                "symbol": symbol,
                "alpha": alpha_value,
            }

        return result

    def get_rankings(self) -> list[tuple[str, float]]:
        """Get current alpha rankings."""
        return self._rankings.copy()

    def reset(self) -> None:
        """Reset strategy state."""
        self._combined_alpha.clear()
        self._current_signals.clear()
        self._last_refresh = None
        self._rankings.clear()
        self._current_weights = None

    def get_current_weights(self) -> Optional[WeightResult]:
        """Get current alpha weights."""
        return self._current_weights

    def set_weight_model(self, weight_model: AlphaWeightModel) -> None:
        """Update the weight model. Forces refresh on next signal generation."""
        self.weight_model = weight_model
        self._last_refresh = None
        logger.info(f"Weight model updated to {weight_model.name}")
