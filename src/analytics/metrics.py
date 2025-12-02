"""
Performance metrics for backtesting results.

Calculate standard trading metrics including:
- Returns (total, annualized, CAGR)
- Risk metrics (volatility, Sharpe, Sortino)
- Drawdown metrics (max drawdown, Calmar ratio)
- Trade statistics (win rate, profit factor)
"""
import numpy as np
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime


class PerformanceMetrics:
    """Calculate performance metrics from equity curve and trade data."""

    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate

    def calculate_all(
        self,
        equity_curve: pd.Series,
        trades: Optional[List[Dict]] = None,
        returns: Optional[pd.Series] = None
    ) -> Dict:
        """
        Calculate all performance metrics.

        :param equity_curve: Time series of portfolio value
        :param trades: List of trade dictionaries (optional, for trade-based metrics)
        :param returns: Pre-calculated returns series (optional, computed if not provided)

        :return: Dictionary of all metrics
        """
        if returns is None:
            returns = equity_curve.pct_change().dropna()

        metrics = {
            # Return metrics
            'total_return': self.total_return(equity_curve),
            'cagr': self.cagr(equity_curve),
            'annualized_return': self.annualized_return(returns),

            # Risk metrics
            'volatility': self.volatility(returns),
            'sharpe_ratio': self.sharpe_ratio(returns),
            'sortino_ratio': self.sortino_ratio(returns),

            # Drawdown metrics
            'max_drawdown': self.max_drawdown(equity_curve),
            'max_drawdown_duration': self.max_drawdown_duration(equity_curve),
            'calmar_ratio': self.calmar_ratio(equity_curve),

            # Additional stats
            'best_day': returns.max(),
            'worst_day': returns.min(),
            'positive_days': (returns > 0).sum(),
            'negative_days': (returns < 0).sum(),
            'win_rate_daily': (returns > 0).sum() / len(returns) if len(returns) > 0 else 0,
        }

        # Add trade-based metrics if trades provided
        if trades:
            trade_metrics = self.trade_statistics(trades)
            metrics.update(trade_metrics)

        return metrics

    def total_return(self, equity_curve: pd.Series) -> float:
        """Calculate total return percentage."""
        if len(equity_curve) < 2:
            return 0.0
        return (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1

    def cagr(self, equity_curve: pd.Series) -> float:
        """
        Calculate Compound Annual Growth Rate.

        CAGR = (Ending Value / Beginning Value)^(1/Years) - 1
        """
        if len(equity_curve) < 2:
            return 0.0

        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0])

        # Calculate time period in years
        if isinstance(equity_curve.index, pd.DatetimeIndex):
            days = (equity_curve.index[-1] - equity_curve.index[0]).days
            years = days / 365.25
        else:
            # Assume daily data if no datetime index
            years = len(equity_curve) / 252  # 252 trading days per year

        if years == 0:
            return 0.0

        cagr = (total_return ** (1 / years)) - 1
        return cagr

    def annualized_return(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """
        Calculate annualized return from return series.

        Args:
            returns: Series of period returns
            periods_per_year: Number of periods in a year (252 for daily, 12 for monthly)
        """
        if len(returns) == 0:
            return 0.0
        mean_return = returns.mean()
        return (1 + mean_return) ** periods_per_year - 1

    def volatility(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """
        Calculate annualized volatility (standard deviation of returns).

        Args:
            returns: Series of period returns
            periods_per_year: Number of periods in a year
        """
        if len(returns) < 2:
            return 0.0
        return returns.std() * np.sqrt(periods_per_year)

    def sharpe_ratio(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """
        Calculate Sharpe Ratio.

        Sharpe = (Annualized Return - Risk Free Rate) / Annualized Volatility
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - (self.risk_free_rate / periods_per_year)

        if excess_returns.std() == 0:
            return 0.0

        sharpe = np.sqrt(periods_per_year) * (excess_returns.mean() / excess_returns.std())
        return sharpe

    def sortino_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252,
        target_return: float = 0.0
    ) -> float:
        """
        Calculate Sortino Ratio (like Sharpe but only penalizes downside volatility).

        Sortino = (Annualized Return - Target) / Downside Deviation
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - (target_return / periods_per_year)
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        downside_std = downside_returns.std() * np.sqrt(periods_per_year)
        annualized_return = self.annualized_return(returns, periods_per_year)

        sortino = (annualized_return - target_return) / downside_std
        return sortino

    def max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown.

        Max Drawdown = (Trough Value - Peak Value) / Peak Value
        """
        if len(equity_curve) < 2:
            return 0.0

        cummax = equity_curve.expanding().max()
        drawdown = (equity_curve - cummax) / cummax
        return drawdown.min()

    def max_drawdown_duration(self, equity_curve: pd.Series) -> int:
        """
        Calculate maximum drawdown duration in periods.

        Returns the longest period between new equity highs.
        """
        if len(equity_curve) < 2:
            return 0

        cummax = equity_curve.expanding().max()
        is_new_high = equity_curve == cummax

        # Find periods between new highs
        durations = []
        current_duration = 0

        for high in is_new_high:
            if high:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0
            else:
                current_duration += 1

        # Add final duration if still in drawdown
        if current_duration > 0:
            durations.append(current_duration)

        return max(durations) if durations else 0

    def calmar_ratio(self, equity_curve: pd.Series) -> float:
        """
        Calculate Calmar Ratio.

        Calmar = CAGR / Absolute(Max Drawdown)
        """
        max_dd = abs(self.max_drawdown(equity_curve))
        if max_dd == 0:
            return 0.0

        cagr_val = self.cagr(equity_curve)
        return cagr_val / max_dd

    def trade_statistics(self, trades: List[Dict]) -> Dict:
        """
        Calculate trade-based statistics.

        Args:
            trades: List of trade dicts with 'pnl', 'return', etc.

        Returns:
            Dictionary of trade statistics
        """
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'avg_trade_pnl': 0.0,
            }

        pnls = [t.get('pnl', 0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        total_trades = len(trades)
        winning_trades = len(wins)
        losing_trades = len(losses)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'largest_win': max(pnls) if pnls else 0,
            'largest_loss': min(pnls) if pnls else 0,
            'avg_trade_pnl': np.mean(pnls) if pnls else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
        }


def format_metrics(metrics: Dict) -> str:
    """
    Format metrics dictionary into a readable string report.

    Args:
        metrics: Dictionary of performance metrics

    Returns:
        Formatted string report
    """
    report = []
    report.append("=" * 70)
    report.append("PERFORMANCE METRICS")
    report.append("=" * 70)

    # Return metrics
    report.append("\nReturn Metrics:")
    report.append(f"  Total Return:        {metrics.get('total_return', 0):>10.2%}")
    report.append(f"  CAGR:                {metrics.get('cagr', 0):>10.2%}")
    report.append(f"  Annualized Return:   {metrics.get('annualized_return', 0):>10.2%}")

    # Risk metrics
    report.append("\nRisk Metrics:")
    report.append(f"  Volatility:          {metrics.get('volatility', 0):>10.2%}")
    report.append(f"  Sharpe Ratio:        {metrics.get('sharpe_ratio', 0):>10.2f}")
    report.append(f"  Sortino Ratio:       {metrics.get('sortino_ratio', 0):>10.2f}")

    # Drawdown metrics
    report.append("\nDrawdown Metrics:")
    report.append(f"  Max Drawdown:        {metrics.get('max_drawdown', 0):>10.2%}")
    report.append(f"  Max DD Duration:     {metrics.get('max_drawdown_duration', 0):>10.0f} periods")
    report.append(f"  Calmar Ratio:        {metrics.get('calmar_ratio', 0):>10.2f}")

    # Trade statistics (if available)
    if 'total_trades' in metrics:
        report.append("\nTrade Statistics:")
        report.append(f"  Total Trades:        {metrics.get('total_trades', 0):>10.0f}")
        report.append(f"  Winning Trades:      {metrics.get('winning_trades', 0):>10.0f}")
        report.append(f"  Losing Trades:       {metrics.get('losing_trades', 0):>10.0f}")
        report.append(f"  Win Rate:            {metrics.get('win_rate', 0):>10.2%}")
        report.append(f"  Profit Factor:       {metrics.get('profit_factor', 0):>10.2f}")
        report.append(f"  Avg Win:             ${metrics.get('avg_win', 0):>10.2f}")
        report.append(f"  Avg Loss:            ${metrics.get('avg_loss', 0):>10.2f}")
        report.append(f"  Largest Win:         ${metrics.get('largest_win', 0):>10.2f}")
        report.append(f"  Largest Loss:        ${metrics.get('largest_loss', 0):>10.2f}")

    report.append("=" * 70)
    return "\n".join(report)


if __name__ == '__main__':
    # Example usage
    print("=" * 70)
    print("Performance Metrics Example")
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
        {'pnl': 500, 'return': 0.05},
        {'pnl': -200, 'return': -0.02},
        {'pnl': 300, 'return': 0.03},
        {'pnl': -150, 'return': -0.015},
        {'pnl': 700, 'return': 0.07},
        {'pnl': -100, 'return': -0.01},
        {'pnl': 400, 'return': 0.04},
    ]

    # Calculate metrics
    metrics_calc = PerformanceMetrics(risk_free_rate=0.02)
    metrics = metrics_calc.calculate_all(equity_curve, trades=trades)

    # Print formatted report
    print(format_metrics(metrics))

    print("\nEquity Curve Summary:")
    print(f"  Starting Value: ${equity_curve.iloc[0]:,.2f}")
    print(f"  Ending Value:   ${equity_curve.iloc[-1]:,.2f}")
    print(f"  Peak Value:     ${equity_curve.max():,.2f}")
    print(f"  Trough Value:   ${equity_curve.min():,.2f}")
