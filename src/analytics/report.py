"""
Simplified markdown report generator for backtesting results.

Generates concise markdown reports with:
- Key performance metrics (Sharpe ratio, max drawdown, win ratio, profit-loss ratio)
- PnL curve chart
"""
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from analytics.metrics import PerformanceMetrics
from analytics.visualizer import BacktestVisualizer


class MarkdownReportGenerator:
    """
    Generate simplified markdown reports for backtest results.
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize report generator.

        Args:
            output_dir: Directory to save reports (default: docs/reports)
        """
        if output_dir is None:
            output_dir = os.getenv('REPORTS_PATH', 'docs/reports')

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.charts_dir = self.output_dir / 'charts'
        self.charts_dir.mkdir(exist_ok=True)

    def generate_report(
        self,
        strategy_name: str,
        equity_curve: pd.Series,
        trades: List[Dict],
        config: Optional[Dict] = None,
    ) -> str:
        """
        Generate a complete markdown report.

        Args:
            strategy_name: Name of the strategy
            equity_curve: Time series of portfolio value
            trades: List of trade dictionaries
            config: Optional configuration parameters used

        Returns:
            Path to the generated report file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_name = f"{strategy_name}_{timestamp}.md"
        report_path = self.output_dir / report_name

        # Calculate metrics
        metrics_calc = PerformanceMetrics()
        metrics = metrics_calc.calculate_all(equity_curve, trades)

        # Generate PnL chart
        chart_filename = f"{strategy_name}_{timestamp}_pnl.png"
        chart_path = self.charts_dir / chart_filename
        viz = BacktestVisualizer()
        viz.plot_pnl_curve(equity_curve, save_path=str(chart_path))

        # Build report sections
        sections = []

        # Header
        sections.append(self._generate_header(strategy_name, timestamp))

        # Summary
        sections.append(self._generate_summary(equity_curve, trades, metrics))

        # Configuration
        if config:
            sections.append(self._generate_config_section(config))

        # Performance Metrics
        sections.append(self._generate_metrics_section(metrics))

        # PnL Chart
        sections.append(self._generate_chart_section(chart_filename))

        # Footer
        sections.append(self._generate_footer())

        # Write report
        report_content = '\n\n'.join(sections)
        report_path.write_text(report_content)

        return str(report_path)

    def _generate_header(self, strategy_name: str, timestamp: str) -> str:
        """Generate report header."""
        date_str = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%B %d, %Y at %H:%M:%S')

        return f"""# Backtest Report: {strategy_name}

**Generated:** {date_str}

---"""

    def _generate_summary(self, equity_curve: pd.Series, trades: List[Dict], metrics: Dict) -> str:
        """Generate executive summary section."""
        initial_capital = equity_curve.iloc[0]
        final_capital = equity_curve.iloc[-1]
        total_return = (final_capital - initial_capital) / initial_capital
        num_trades = len(trades)

        sharpe = metrics.get('sharpe_ratio', 0)
        max_dd = metrics.get('max_drawdown', 0)

        return f"""## Summary

| Metric | Value |
|--------|-------|
| Initial Capital | ${initial_capital:,.2f} |
| Final Capital | ${final_capital:,.2f} |
| Total Return | {total_return:.2%} |
| Number of Trades | {num_trades} |
| Sharpe Ratio | {sharpe:.3f} |
| Max Drawdown | {max_dd:.2%} |"""

    def _generate_config_section(self, config: Dict) -> str:
        """Generate configuration section."""
        lines = ["## Configuration\n"]
        lines.append("| Parameter | Value |")
        lines.append("|-----------|-------|")

        for key, value in config.items():
            if isinstance(value, float):
                value_str = f"{value:.4f}" if abs(value) < 1 else f"{value:,.2f}"
            else:
                value_str = str(value)
            lines.append(f"| {key} | {value_str} |")

        return '\n'.join(lines)

    def _generate_metrics_section(self, metrics: Dict) -> str:
        """Generate performance metrics section."""
        sharpe = metrics.get('sharpe_ratio', 0)
        max_dd = metrics.get('max_drawdown', 0)
        win_ratio = metrics.get('win_ratio', 0)
        pl_ratio = metrics.get('profit_loss_ratio', 0)

        return f"""## Performance Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Sharpe Ratio | {sharpe:.3f} | {self._interpret_sharpe(sharpe)} |
| Max Drawdown | {max_dd:.2%} | {self._interpret_drawdown(max_dd)} |
| Win Ratio | {win_ratio:.2%} | {self._interpret_win_ratio(win_ratio)} |
| Profit/Loss Ratio | {pl_ratio:.3f} | {self._interpret_pl_ratio(pl_ratio)} |

### Metric Definitions

- **Sharpe Ratio**: Risk-adjusted return. Higher is better. >1.0 is good, >2.0 is excellent.
- **Max Drawdown**: Largest peak-to-trough decline. Closer to 0% is better.
- **Win Ratio**: Percentage of winning trades. 50%+ is generally good.
- **Profit/Loss Ratio**: Average win divided by average loss. >1.0 means wins exceed losses."""

    def _generate_chart_section(self, chart_filename: str) -> str:
        """Generate chart section."""
        rel_path = f"charts/{chart_filename}"
        return f"""## PnL Curve

![PnL Curve]({rel_path})"""

    def _generate_footer(self) -> str:
        """Generate report footer."""
        return f"""---

*Report generated by Trading System Backtester on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"""

    # Interpretation helpers

    def _interpret_sharpe(self, sharpe: float) -> str:
        if sharpe >= 2.0:
            return "Excellent"
        elif sharpe >= 1.0:
            return "Good"
        elif sharpe >= 0.5:
            return "Acceptable"
        else:
            return "Poor"

    def _interpret_drawdown(self, dd: float) -> str:
        dd_pct = abs(dd) * 100
        if dd_pct < 10:
            return "Low risk"
        elif dd_pct < 20:
            return "Moderate risk"
        elif dd_pct < 30:
            return "High risk"
        else:
            return "Very high risk"

    def _interpret_win_ratio(self, wr: float) -> str:
        if wr >= 0.60:
            return "High"
        elif wr >= 0.50:
            return "Good"
        elif wr >= 0.40:
            return "Acceptable"
        else:
            return "Low"

    def _interpret_pl_ratio(self, pl: float) -> str:
        if pl >= 2.0:
            return "Excellent"
        elif pl >= 1.5:
            return "Good"
        elif pl >= 1.0:
            return "Acceptable"
        else:
            return "Poor"


if __name__ == '__main__':
    import numpy as np

    print("=" * 70)
    print("Markdown Report Generator Example")
    print("=" * 70)

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    returns = np.random.normal(0.0008, 0.012, 252)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    equity_curve = pd.Series(equity.values, index=dates)

    # Sample trades
    trades = []
    for i in range(30):
        trade_return = np.random.normal(0.02, 0.05)
        trades.append({'pnl': trade_return * 10000})

    # Configuration
    config = {
        'initial_capital': 100000,
        'position_size': 0.10,
        'risk_free_rate': 0.02,
    }

    # Generate report
    generator = MarkdownReportGenerator(output_dir='docs/reports')
    report_path = generator.generate_report(
        strategy_name='TestStrategy',
        equity_curve=equity_curve,
        trades=trades,
        config=config,
    )

    print(f"\nReport generated: {report_path}")
    print(f"Charts saved to: {generator.charts_dir}")
