"""
Simplified backtest results analyzer.

Analyzes trades and equity curve to generate performance reports.
"""
import pandas as pd
from typing import List, Dict
from analytics.metrics import PerformanceMetrics, format_metrics


class BacktestAnalyzer:
    """
    Analyze backtest results using simplified metrics.
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize backtest analyzer.

        Args:
            risk_free_rate: Annual risk-free rate for metrics calculation
        """
        self.metrics_calc = PerformanceMetrics(risk_free_rate=risk_free_rate)
        self.trades = []
        self.equity_curve = None

    def add_trade(self, trade: Dict) -> None:
        """
        Add a completed trade to the analyzer.

        Trade dict should contain at minimum:
            - pnl: float (profit/loss)

        Args:
            trade: Trade dictionary
        """
        self.trades.append(trade)

    def set_equity_curve(self, equity_curve: pd.Series) -> None:
        """
        Set the equity curve time series.

        Args:
            equity_curve: Time series of portfolio values
        """
        self.equity_curve = equity_curve

    def analyze(self) -> Dict:
        """
        Perform analysis of backtest results.

        Returns:
            Dictionary containing:
            - metrics: Performance metrics (Sharpe, drawdown, win ratio, P/L ratio)
            - num_trades: Number of trades
            - equity_info: Basic equity curve statistics
        """
        if self.equity_curve is None or len(self.equity_curve) == 0:
            return {
                'error': 'No equity curve data available',
                'metrics': {},
                'num_trades': len(self.trades),
            }

        # Calculate metrics
        metrics = self.metrics_calc.calculate_all(self.equity_curve, self.trades)

        # Basic equity statistics
        initial_value = self.equity_curve.iloc[0]
        final_value = self.equity_curve.iloc[-1]
        total_return = (final_value - initial_value) / initial_value

        results = {
            'metrics': metrics,
            'num_trades': len(self.trades),
            'equity_info': {
                'initial_value': initial_value,
                'final_value': final_value,
                'total_return': total_return,
                'num_ticks': len(self.equity_curve),
            }
        }

        return results

    def generate_report(self) -> str:
        """
        Generate text report of backtest results.

        Returns:
            Formatted string report
        """
        analysis = self.analyze()

        if 'error' in analysis:
            return f"Error: {analysis['error']}"

        report = []
        report.append("=" * 70)
        report.append("BACKTEST ANALYSIS REPORT")
        report.append("=" * 70)

        # Equity info
        equity_info = analysis.get('equity_info', {})
        report.append("\nEquity Curve Summary:")
        report.append(f"  Initial Value:  ${equity_info.get('initial_value', 0):>12,.2f}")
        report.append(f"  Final Value:    ${equity_info.get('final_value', 0):>12,.2f}")
        report.append(f"  Total Return:   {equity_info.get('total_return', 0):>12.2%}")
        report.append(f"  Number of Ticks: {equity_info.get('num_ticks', 0):>12,}")

        # Trade info
        report.append(f"\nTotal Trades:     {analysis.get('num_trades', 0):>12,}")

        # Performance metrics
        if 'metrics' in analysis:
            report.append("\n" + format_metrics(analysis['metrics']))

        report.append("=" * 70)
        return "\n".join(report)

    def get_trades_list(self) -> List[Dict]:
        """
        Get list of all trades.

        Returns:
            List of trade dictionaries
        """
        return self.trades

    def get_trades_df(self) -> pd.DataFrame:
        """
        Get trades as a DataFrame.

        Returns:
            DataFrame of all trades
        """
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame(self.trades)


if __name__ == '__main__':
    import numpy as np

    print("=" * 70)
    print("Backtest Analyzer Example")
    print("=" * 70)

    # Create analyzer
    analyzer = BacktestAnalyzer(risk_free_rate=0.02)

    # Generate sample equity curve
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    np.random.seed(42)
    returns = np.random.normal(0.0008, 0.012, 252)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    equity_curve = pd.Series(equity.values, index=pd.DatetimeIndex(dates))
    analyzer.set_equity_curve(equity_curve)

    # Add sample trades
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

    for trade in trades:
        analyzer.add_trade(trade)

    # Generate report
    print(analyzer.generate_report())

    # Show trades DataFrame
    print("\nTrades DataFrame:")
    print(analyzer.get_trades_df())
