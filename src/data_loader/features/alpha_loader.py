"""
Alpha data loading and caching layer.

Wraps quantdl client for loading alpha signals with TTL-based caching.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class AlphaLoaderConfig:
    """Configuration for AlphaLoader."""

    bucket: str = "us-equity-datalake"
    cache_ttl_minutes: int = 60
    lookback_days: int = 252


@dataclass
class CacheEntry:
    """Cache entry with timestamp."""

    data: pl.DataFrame
    timestamp: datetime


class AlphaLoader:
    """
    Alpha data loading with TTL-based caching.

    Wraps quantdl client for fetching alpha signals. Supports built-in
    alpha formulas and external alpha data.

    Example:
        config = AlphaLoaderConfig(cache_ttl_minutes=60)
        loader = AlphaLoader(config)
        alpha_df = loader.load_alpha("momentum_20d", ["AAPL", "MSFT"], start, end)
        values = loader.get_alpha_for_date("momentum_20d", ["AAPL", "MSFT"], date)
    """

    # Built-in alpha formulas
    BUILTIN_ALPHAS = {"momentum_20d", "mean_reversion", "cross_sectional_momentum"}

    def __init__(
        self,
        config: Optional[AlphaLoaderConfig] = None,
        client: Optional[object] = None,  # QuantDLClient when available
    ):
        """
        Initialize alpha loader.

        Args:
            config: Loader configuration
            client: Optional quantdl client (uses default if not provided)
        """
        self.config = config or AlphaLoaderConfig()
        self._client = client
        self._cache: dict[str, CacheEntry] = {}

    def _get_cache_key(
        self,
        alpha_name: str,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> str:
        """Generate cache key from parameters."""
        symbols_str = ",".join(sorted(symbols))
        return f"{alpha_name}:{symbols_str}:{start.date()}:{end.date()}"

    def _is_cache_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid."""
        age = datetime.now() - entry.timestamp
        return age < timedelta(minutes=self.config.cache_ttl_minutes)

    def load_alpha(
        self,
        alpha_name: str,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """
        Load alpha data for symbols in date range.

        Args:
            alpha_name: Name of alpha (e.g., "momentum_20d")
            symbols: List of stock symbols
            start: Start datetime
            end: End datetime

        Returns:
            Polars DataFrame with columns: date, symbol, alpha_value
        """
        cache_key = self._get_cache_key(alpha_name, symbols, start, end)

        # Check cache
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if self._is_cache_valid(entry):
                logger.debug(f"Cache hit for {alpha_name}")
                return entry.data

        # Load data
        if alpha_name in self.BUILTIN_ALPHAS:
            df = self._calculate_builtin_alpha(alpha_name, symbols, start, end)
        else:
            df = self._load_from_quantdl(alpha_name, symbols, start, end)

        # Cache result
        self._cache[cache_key] = CacheEntry(data=df, timestamp=datetime.now())
        logger.info(f"Loaded alpha {alpha_name} for {len(symbols)} symbols")

        return df

    def get_alpha_for_date(
        self,
        alpha_name: str,
        symbols: list[str],
        date: datetime,
    ) -> dict[str, float]:
        """
        Get alpha values for a specific date.

        Args:
            alpha_name: Name of alpha
            symbols: List of stock symbols
            date: Target date

        Returns:
            Dictionary mapping symbol -> alpha value
        """
        # Load with lookback
        start = date - timedelta(days=self.config.lookback_days)
        df = self.load_alpha(alpha_name, symbols, start, date)

        if df.is_empty():
            return {symbol: 0.0 for symbol in symbols}

        # Filter to target date
        date_only = date.date() if hasattr(date, "date") else date
        filtered = df.filter(pl.col("date") == date_only)

        if filtered.is_empty():
            # Use most recent date
            latest_date = df.select(pl.col("date").max()).item()
            filtered = df.filter(pl.col("date") == latest_date)

        # Convert to dict
        result = {}
        for row in filtered.iter_rows(named=True):
            result[row["symbol"]] = row["alpha_value"]

        # Fill missing symbols with 0
        for symbol in symbols:
            if symbol not in result:
                result[symbol] = 0.0

        return result

    def _calculate_builtin_alpha(
        self,
        alpha_name: str,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """Calculate built-in alpha formula."""
        if alpha_name == "momentum_20d":
            return self._calc_momentum_20d(symbols, start, end)
        elif alpha_name == "mean_reversion":
            return self._calc_mean_reversion(symbols, start, end)
        elif alpha_name == "cross_sectional_momentum":
            return self._calc_cross_sectional_momentum(symbols, start, end)
        else:
            raise ValueError(f"Unknown built-in alpha: {alpha_name}")

    def _calc_momentum_20d(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """
        Calculate 20-day momentum alpha.

        Formula: rank(zscore(20d returns))
        """
        # For now, return placeholder data
        # In production, would fetch prices and calculate
        dates = pl.date_range(start.date(), end.date(), eager=True)
        rows = []
        for date in dates:
            for i, symbol in enumerate(symbols):
                # Placeholder: spread values evenly
                alpha_value = (i - len(symbols) / 2) / len(symbols)
                rows.append(
                    {"date": date, "symbol": symbol, "alpha_value": alpha_value}
                )

        return pl.DataFrame(rows)

    def _calc_mean_reversion(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """
        Calculate mean reversion alpha.

        Formula: -rank(deviation from 20d mean)
        """
        dates = pl.date_range(start.date(), end.date(), eager=True)
        rows = []
        for date in dates:
            for i, symbol in enumerate(symbols):
                # Placeholder: inverse of momentum
                alpha_value = -(i - len(symbols) / 2) / len(symbols)
                rows.append(
                    {"date": date, "symbol": symbol, "alpha_value": alpha_value}
                )

        return pl.DataFrame(rows)

    def _calc_cross_sectional_momentum(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """
        Calculate cross-sectional momentum alpha.

        Formula: scale(rank(returns))
        """
        dates = pl.date_range(start.date(), end.date(), eager=True)
        rows = []
        for date in dates:
            for i, symbol in enumerate(symbols):
                # Placeholder: scaled rank
                alpha_value = 2 * (i / max(len(symbols) - 1, 1)) - 1
                rows.append(
                    {"date": date, "symbol": symbol, "alpha_value": alpha_value}
                )

        return pl.DataFrame(rows)

    def _load_from_quantdl(
        self,
        alpha_name: str,
        symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """Load alpha data from quantdl."""
        if self._client is None:
            logger.warning(
                f"No quantdl client configured, returning empty for {alpha_name}"
            )
            return pl.DataFrame({"date": [], "symbol": [], "alpha_value": []})

        # TODO: Implement quantdl integration
        # df = self._client.fetch(alpha_name, symbols, start, end)
        # return df
        raise NotImplementedError("quantdl integration not yet implemented")

    def clear_cache(self, alpha_name: Optional[str] = None) -> None:
        """
        Clear cached data.

        Args:
            alpha_name: Specific alpha to clear (None clears all)
        """
        if alpha_name:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{alpha_name}:")]
            for key in keys_to_remove:
                del self._cache[key]
            logger.debug(f"Cleared cache for {alpha_name}")
        else:
            self._cache.clear()
            logger.debug("Cleared all alpha cache")
