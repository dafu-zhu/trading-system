"""
Simplified performance metrics for backtesting results.

Calculates only the essential metrics:
- Sharpe Ratio
- Maximum Drawdown
- Win Ratio (from trades)
- Profit-and-Loss Ratio (avg win / avg loss)
"""
import numpy as np
import pandas as pd
from typing import List, Dict


class PerformanceMetrics:
    """Calculate essential performance metrics from equity curve and trades."""

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe ratio calculation
        """
        self.risk_free_rate = risk_free_rate

    def calculate_all(
        self,
        equity_curve: pd.Series,
        trades: List[Dict],
        periods_per_year: int = 252
    ) -> Dict:
        """
        Calculate all essential performance metrics.

        Args:
            equity_curve: Time series of portfolio value
            trades: List of trade dictionaries with 'pnl' field
            periods_per_year: Number of periods in a year (default 252 for daily)

        Returns:
            Dictionary containing:
            - sharpe_ratio: Risk-adjusted return metric
            - max_drawdown: Maximum peak-to-trough decline
            - win_ratio: Percentage of winning trades
            - profit_loss_ratio: Average win divided by average loss
        """
        # Calculate returns
        returns = equity_curve.pct_change().dropna()

        metrics = {
            'sharpe_ratio': self.sharpe_ratio(returns, periods_per_year),
            'max_drawdown': self.max_drawdown(equity_curve),
            'win_ratio': self.win_ratio(trades),
            'profit_loss_ratio': self.profit_loss_ratio(trades),
        }

        return metrics

    def sharpe_ratio(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """
        Calculate Sharpe Ratio.

        Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns
        Result is annualized.

        Args:
            returns: Series of period returns
            periods_per_year: Number of periods in a year

        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        # Calculate excess returns
        excess_returns = returns - (self.risk_free_rate / periods_per_year)

        if excess_returns.std() == 0:
            return 0.0

        # Annualize the Sharpe ratio
        sharpe = np.sqrt(periods_per_year) * (excess_returns.mean() / excess_returns.std())
        return sharpe

    def max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown.

        Max Drawdown = (Trough Value - Peak Value) / Peak Value

        Args:
            equity_curve: Time series of portfolio value

        Returns:
            Maximum drawdown as negative decimal (e.g., -0.15 for 15% drawdown)
        """
        if len(equity_curve) < 2:
            return 0.0

        # Calculate running maximum
        cummax = equity_curve.expanding().max()

        # Calculate drawdown at each point
        drawdown = (equity_curve - cummax) / cummax

        # Return the maximum drawdown (most negative value)
        return drawdown.min()

    def win_ratio(self, trades: List[Dict]) -> float:
        """
        Calculate win ratio (percentage of winning trades).

        Args:
            trades: List of trade dictionaries with 'pnl' field

        Returns:
            Win ratio as decimal (e.g., 0.60 for 60% win rate)
        """
        if not trades:
            return 0.0

        pnls = [t.get('pnl', 0) for t in trades]
        winning_trades = sum(1 for pnl in pnls if pnl > 0)

        return winning_trades / len(trades)

    def profit_loss_ratio(self, trades: List[Dict]) -> float:
        """
        Calculate profit-and-loss ratio (average win / average loss).

        Also known as the win/loss ratio or payoff ratio.
        Higher is better - values above 1.0 mean average wins exceed average losses.

        Args:
            trades: List of trade dictionaries with 'pnl' field

        Returns:
            Profit-loss ratio (e.g., 2.0 means avg win is 2x avg loss)
        """
        if not trades:
            return 0.0

        pnls = [t.get('pnl', 0) for t in trades]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]

        if not wins or not losses:
            return 0.0

        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))

        if avg_loss == 0:
            return 0.0

        return avg_win / avg_loss


def format_metrics(metrics: Dict) -> str:
    """
    Format metrics dictionary into a readable string report.

    Args:
        metrics: Dictionary of performance metrics

    Returns:
        Formatted string report
    """
    report = []
    report.append("=" * 50)
    report.append("PERFORMANCE METRICS")
    report.append("=" * 50)

    sharpe = metrics.get('sharpe_ratio', 0)
    max_dd = metrics.get('max_drawdown', 0)
    win_ratio = metrics.get('win_ratio', 0)
    pl_ratio = metrics.get('profit_loss_ratio', 0)

    report.append(f"\nSharpe Ratio:        {sharpe:>10.3f}")
    report.append(f"Max Drawdown:        {max_dd:>10.2%}")
    report.append(f"Win Ratio:           {win_ratio:>10.2%}")
    report.append(f"Profit/Loss Ratio:   {pl_ratio:>10.3f}")

    report.append("=" * 50)
    return "\n".join(report)


if __name__ == '__main__':
    print("=" * 70)
    print("Simplified Performance Metrics Example")
    print("=" * 70)

    # Generate sample equity curve
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')

    # Simulate returns with slight positive drift
    returns = np.random.normal(0.0005, 0.01, 252)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    equity_curve = pd.Series(equity.values, index=dates)

    # Sample trades
    trades = [
        {'pnl': 500},
        {'pnl': -200},
        {'pnl': 300},
        {'pnl': -150},
        {'pnl': 700},
        {'pnl': -100},
        {'pnl': 400},
        {'pnl': -250},
        {'pnl': 600},
        {'pnl': -180},
    ]

    # Calculate metrics
    metrics_calc = PerformanceMetrics(risk_free_rate=0.02)
    metrics = metrics_calc.calculate_all(equity_curve, trades=trades)

    # Print formatted report
    print(format_metrics(metrics))

    print("\nEquity Curve Summary:")
    print(f"  Starting Value: ${equity_curve.iloc[0]:,.2f}")
    print(f"  Ending Value:   ${equity_curve.iloc[-1]:,.2f}")
    print(f"  Total Return:   {(equity_curve.iloc[-1]/equity_curve.iloc[0] - 1):.2%}")
