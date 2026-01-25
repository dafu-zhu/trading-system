"""
Equity Tracker: Tracks portfolio value at each tick for accurate PnL tracking.

This tracker records the portfolio value at every market data tick,
enabling accurate mark-to-market valuation and PnL curve generation.
"""

from typing import List, Tuple
from datetime import datetime
import pandas as pd


class EquityTracker:
    """
    Tracks portfolio equity at each tick for accurate performance measurement.
    Records timestamp and total portfolio value for PnL curve generation.
    """

    def __init__(self):
        # List of (timestamp, portfolio_value) tuples
        self.equity_history: List[Tuple[datetime, float]] = []

    def record_tick(self, timestamp: datetime, portfolio_value: float) -> None:
        """
        Record portfolio value at a specific timestamp.

        Args:
            timestamp: Time of the snapshot
            portfolio_value: Total portfolio value (cash + positions)
        """
        self.equity_history.append((timestamp, portfolio_value))

    def get_equity_series(self) -> pd.Series:
        """
        Get equity curve as a pandas Series.

        Returns:
            Time series of portfolio values indexed by timestamp
        """
        if not self.equity_history:
            return pd.Series(dtype=float)

        timestamps, values = zip(*self.equity_history)
        return pd.Series(values, index=pd.DatetimeIndex(timestamps))

    def get_returns_series(self) -> pd.Series:
        """
        Calculate returns series from equity curve.

        Returns:
            Time series of tick-by-tick returns
        """
        equity = self.get_equity_series()
        if len(equity) < 2:
            return pd.Series(dtype=float)
        return equity.pct_change().dropna()

    def get_current_equity(self) -> float:
        """
        Get the most recent portfolio value.

        Returns:
            Latest portfolio value, or 0.0 if no history
        """
        if not self.equity_history:
            return 0.0
        return self.equity_history[-1][1]

    def get_initial_equity(self) -> float:
        """
        Get the initial portfolio value.

        Returns:
            First portfolio value, or 0.0 if no history
        """
        if not self.equity_history:
            return 0.0
        return self.equity_history[0][1]

    def get_total_return(self) -> float:
        """
        Calculate total return percentage.

        Returns:
            Total return as a decimal (e.g., 0.15 for 15% return)
        """
        initial = self.get_initial_equity()
        if initial == 0:
            return 0.0
        current = self.get_current_equity()
        return (current - initial) / initial

    def get_tick_count(self) -> int:
        """
        Get number of recorded ticks.

        Returns:
            Number of equity snapshots
        """
        return len(self.equity_history)

    def clear(self) -> None:
        """Clear all recorded equity history."""
        self.equity_history.clear()
