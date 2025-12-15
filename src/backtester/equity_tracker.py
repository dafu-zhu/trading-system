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


if __name__ == '__main__':
    from datetime import timedelta

    print("=" * 70)
    print("Equity Tracker Example")
    print("=" * 70)

    # Create tracker
    tracker = EquityTracker()

    # Simulate recording equity at multiple ticks
    base_time = datetime(2023, 1, 1, 9, 30)
    initial_capital = 100000

    # Simulate some price movements
    for i in range(100):
        timestamp = base_time + timedelta(minutes=i)
        # Simulate portfolio value changes
        value = initial_capital * (1 + 0.001 * i + 0.01 * (i % 10 - 5))
        tracker.record_tick(timestamp, value)

    # Get statistics
    print(f"\nTick Count: {tracker.get_tick_count()}")
    print(f"Initial Equity: ${tracker.get_initial_equity():,.2f}")
    print(f"Current Equity: ${tracker.get_current_equity():,.2f}")
    print(f"Total Return: {tracker.get_total_return():.2%}")

    # Get equity series
    equity_series = tracker.get_equity_series()
    print(f"\nEquity Series Length: {len(equity_series)}")
    print(f"First 5 values:")
    print(equity_series.head())

    # Get returns
    returns = tracker.get_returns_series()
    print(f"\nReturns Series Length: {len(returns)}")
    print(f"Mean Return: {returns.mean():.6f}")
    print(f"Return Std: {returns.std():.6f}")
