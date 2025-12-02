"""
Markdown report generator for backtesting results.

Generates comprehensive markdown reports that can be saved to docs/reports/.
Includes performance metrics, trade analysis, and visualizations.
"""
import os
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from analytics.metrics import PerformanceMetrics, format_metrics
from analytics.analyzer import BacktestAnalyzer
from analytics.visualizer import BacktestVisualizer


class MarkdownReportGenerator:
    """
    Generate markdown reports for backtest results.

    Creates professional markdown documents with:
    - Executive summary
    - Performance metrics tables
    - Trade analysis
    - Risk analysis
    - Charts and visualizations
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        include_charts: bool = True
    ):
        """
        Initialize report generator.

        Args:
            output_dir: Directory to save reports (default: docs/reports)
            include_charts: Whether to include chart images in report
        """
        if output_dir is None:
            # Use environment variable or default
            output_dir = os.getenv('REPORTS_PATH', 'docs/reports')

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.include_charts = include_charts

        # Create subdirectories
        self.charts_dir = self.output_dir / 'charts'
        if self.include_charts:
            self.charts_dir.mkdir(exist_ok=True)

    def generate_report(
        self,
        strategy_name: str,
        equity_curve: pd.Series,
        trades: List[Dict],
        metrics: Dict,
        config: Optional[Dict] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Generate a complete markdown report.

        Args:
            strategy_name: Name of the strategy
            equity_curve: Time series of portfolio value
            trades: List of trade dictionaries
            metrics: Dictionary of performance metrics
            config: Optional configuration parameters used
            notes: Optional notes to include in report

        Returns:
            Path to the generated report file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_name = f"{strategy_name}_{timestamp}.md"
        report_path = self.output_dir / report_name

        # Build report sections
        sections = []

        # Header
        sections.append(self._generate_header(strategy_name, timestamp))

        # Executive Summary
        sections.append(self._generate_executive_summary(equity_curve, metrics))

        # Configuration
        if config:
            sections.append(self._generate_config_section(config))

        # Performance Metrics
        sections.append(self._generate_metrics_section(metrics))

        # Trade Analysis
        sections.append(self._generate_trade_analysis(trades, metrics))

        # Risk Analysis
        sections.append(self._generate_risk_analysis(equity_curve, metrics))

        # Visualizations
        if self.include_charts:
            sections.append(self._generate_visualizations(
                strategy_name, timestamp, equity_curve, trades, metrics
            ))

        # Trade Log
        sections.append(self._generate_trade_log(trades))

        # Notes
        if notes:
            sections.append(self._generate_notes(notes))

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

---
"""

    def _generate_executive_summary(self, equity_curve: pd.Series, metrics: Dict) -> str:
        """Generate executive summary section."""
        initial_capital = equity_curve.iloc[0]
        final_capital = equity_curve.iloc[-1]
        total_return = metrics.get('total_return', 0)
        sharpe = metrics.get('sharpe_ratio', 0)
        max_dd = metrics.get('max_drawdown', 0)
        win_rate = metrics.get('win_rate', 0)

        # Performance rating
        if sharpe > 2.0 and max_dd > -0.15:
            rating = "🟢 Excellent"
        elif sharpe > 1.0 and max_dd > -0.25:
            rating = "🟡 Good"
        elif sharpe > 0.5:
            rating = "🟠 Fair"
        else:
            rating = "🔴 Poor"

        return f"""## Executive Summary

**Overall Performance:** {rating}

| Metric | Value |
|--------|-------|
| Initial Capital | ${initial_capital:,.2f} |
| Final Capital | ${final_capital:,.2f} |
| Total Return | {total_return:.2%} |
| Sharpe Ratio | {sharpe:.2f} |
| Max Drawdown | {max_dd:.2%} |
| Win Rate | {win_rate:.2%} |

**Key Takeaways:**
- Strategy {'generated positive returns' if total_return > 0 else 'resulted in losses'} over the backtest period
- Risk-adjusted performance (Sharpe Ratio) is {sharpe:.2f} {'(good)' if sharpe > 1 else '(needs improvement)'}
- Maximum drawdown of {abs(max_dd)*100:.1f}% {'is acceptable' if max_dd > -0.25 else 'is concerning'}
"""

    def _generate_config_section(self, config: Dict) -> str:
        """Generate configuration section."""
        lines = ["## Configuration\n"]
        lines.append("| Parameter | Value |")
        lines.append("|-----------|-------|")

        for key, value in config.items():
            # Format value based on type
            if isinstance(value, float):
                value_str = f"{value:.4f}" if abs(value) < 1 else f"{value:,.2f}"
            else:
                value_str = str(value)
            lines.append(f"| {key} | {value_str} |")

        return '\n'.join(lines)

    def _generate_metrics_section(self, metrics: Dict) -> str:
        """Generate performance metrics section."""
        return f"""## Performance Metrics

### Return Metrics

| Metric | Value |
|--------|-------|
| Total Return | {metrics.get('total_return', 0):.2%} |
| CAGR | {metrics.get('cagr', 0):.2%} |
| Annualized Return | {metrics.get('annualized_return', 0):.2%} |

### Risk Metrics

| Metric | Value |
|--------|-------|
| Volatility (Annual) | {metrics.get('volatility', 0):.2%} |
| Sharpe Ratio | {metrics.get('sharpe_ratio', 0):.3f} |
| Sortino Ratio | {metrics.get('sortino_ratio', 0):.3f} |

### Drawdown Metrics

| Metric | Value |
|--------|-------|
| Max Drawdown | {metrics.get('max_drawdown', 0):.2%} |
| Max DD Duration | {metrics.get('max_drawdown_duration', 0):.0f} periods |
| Calmar Ratio | {metrics.get('calmar_ratio', 0):.3f} |

### Daily Statistics

| Metric | Value |
|--------|-------|
| Best Day | {metrics.get('best_day', 0):.2%} |
| Worst Day | {metrics.get('worst_day', 0):.2%} |
| Positive Days | {metrics.get('positive_days', 0):.0f} |
| Negative Days | {metrics.get('negative_days', 0):.0f} |
| Daily Win Rate | {metrics.get('win_rate_daily', 0):.2%} |
"""

    def _generate_trade_analysis(self, trades: List[Dict], metrics: Dict) -> str:
        """Generate trade analysis section."""
        if not trades:
            return "## Trade Analysis\n\nNo trades executed during backtest period."

        total_trades = metrics.get('total_trades', len(trades))
        winning_trades = metrics.get('winning_trades', 0)
        losing_trades = metrics.get('losing_trades', 0)

        return f"""## Trade Analysis

### Overview

| Metric | Value |
|--------|-------|
| Total Trades | {total_trades:.0f} |
| Winning Trades | {winning_trades:.0f} ({winning_trades/total_trades*100:.1f}%) |
| Losing Trades | {losing_trades:.0f} ({losing_trades/total_trades*100:.1f}%) |
| Win Rate | {metrics.get('win_rate', 0):.2%} |

### Profit/Loss

| Metric | Value |
|--------|-------|
| Gross Profit | ${metrics.get('gross_profit', 0):,.2f} |
| Gross Loss | ${metrics.get('gross_loss', 0):,.2f} |
| Net Profit | ${metrics.get('gross_profit', 0) - metrics.get('gross_loss', 0):,.2f} |
| Profit Factor | {metrics.get('profit_factor', 0):.3f} |
| Average Win | ${metrics.get('avg_win', 0):,.2f} |
| Average Loss | ${metrics.get('avg_loss', 0):,.2f} |
| Largest Win | ${metrics.get('largest_win', 0):,.2f} |
| Largest Loss | ${metrics.get('largest_loss', 0):,.2f} |
| Avg Trade P&L | ${metrics.get('avg_trade_pnl', 0):,.2f} |

### Interpretation

- **Profit Factor:** {self._interpret_profit_factor(metrics.get('profit_factor', 0))}
- **Win Rate:** {self._interpret_win_rate(metrics.get('win_rate', 0))}
- **Avg Win/Loss Ratio:** {self._interpret_win_loss_ratio(metrics.get('avg_win', 0), metrics.get('avg_loss', 0))}
"""

    def _generate_risk_analysis(self, equity_curve: pd.Series, metrics: Dict) -> str:
        """Generate risk analysis section."""
        max_dd = metrics.get('max_drawdown', 0)
        sharpe = metrics.get('sharpe_ratio', 0)
        sortino = metrics.get('sortino_ratio', 0)
        volatility = metrics.get('volatility', 0)

        return f"""## Risk Analysis

### Risk Assessment

| Risk Category | Status | Details |
|---------------|--------|---------|
| Drawdown Risk | {self._risk_status(max_dd, -0.15, -0.30)} | Max DD: {max_dd:.2%} |
| Volatility Risk | {self._risk_status(volatility, 0.20, 0.40, reverse=True)} | Annual Vol: {volatility:.2%} |
| Risk-Adjusted Return | {self._risk_status(sharpe, 1.0, 0.5)} | Sharpe: {sharpe:.2f} |

### Risk Characteristics

- **Maximum Drawdown:** {abs(max_dd)*100:.1f}% drawdown suggests {self._interpret_drawdown(max_dd)}
- **Volatility:** {volatility*100:.1f}% annualized volatility is {self._interpret_volatility(volatility)}
- **Sharpe Ratio:** {sharpe:.2f} indicates {self._interpret_sharpe(sharpe)}
- **Sortino Ratio:** {sortino:.2f} (focuses on downside risk only)

### Recommendations

{self._generate_risk_recommendations(max_dd, sharpe, volatility)}
"""

    def _generate_visualizations(
        self,
        strategy_name: str,
        timestamp: str,
        equity_curve: pd.Series,
        trades: List[Dict],
        metrics: Dict
    ) -> str:
        """Generate visualizations section with embedded images."""
        viz = BacktestVisualizer()

        # Generate charts
        chart_prefix = f"{strategy_name}_{timestamp}"

        # Equity curve
        equity_path = self.charts_dir / f"{chart_prefix}_equity.png"
        viz.plot_equity_curve(equity_curve, save_path=str(equity_path))

        # Drawdown
        dd_path = self.charts_dir / f"{chart_prefix}_drawdown.png"
        viz.plot_drawdown(equity_curve, save_path=str(dd_path))

        # Returns distribution
        returns = equity_curve.pct_change().dropna()
        dist_path = self.charts_dir / f"{chart_prefix}_returns_dist.png"
        viz.plot_returns_distribution(returns, save_path=str(dist_path))

        # Trade analysis (if trades exist)
        if trades:
            trades_path = self.charts_dir / f"{chart_prefix}_trades.png"
            viz.plot_trade_analysis(trades, save_path=str(trades_path))

        # Create markdown with relative paths
        rel_charts_dir = Path('charts')

        sections = [
            "## Visualizations",
            "",
            "### Equity Curve",
            f"![Equity Curve]({rel_charts_dir / f'{chart_prefix}_equity.png'})",
            "",
            "### Drawdown",
            f"![Drawdown]({rel_charts_dir / f'{chart_prefix}_drawdown.png'})",
            "",
            "### Returns Distribution",
            f"![Returns Distribution]({rel_charts_dir / f'{chart_prefix}_returns_dist.png'})",
        ]

        if trades:
            sections.extend([
                "",
                "### Trade Analysis",
                f"![Trade Analysis]({rel_charts_dir / f'{chart_prefix}_trades.png'})",
            ])

        return '\n'.join(sections)

    def _generate_trade_log(self, trades: List[Dict], max_trades: int = 20) -> str:
        """Generate trade log section."""
        if not trades:
            return ""

        df = pd.DataFrame(trades)

        # Select relevant columns
        cols = ['symbol', 'entry_time', 'exit_time', 'entry_price', 'exit_price',
                'quantity', 'pnl', 'return_pct']
        available_cols = [c for c in cols if c in df.columns]

        if not available_cols:
            return ""

        df_display = df[available_cols].copy()

        # Format columns
        if 'entry_time' in df_display:
            df_display['entry_time'] = pd.to_datetime(df_display['entry_time']).dt.strftime('%Y-%m-%d')
        if 'exit_time' in df_display:
            df_display['exit_time'] = pd.to_datetime(df_display['exit_time']).dt.strftime('%Y-%m-%d')
        if 'pnl' in df_display:
            df_display['pnl'] = df_display['pnl'].apply(lambda x: f"${x:,.2f}")
        if 'return_pct' in df_display:
            df_display['return_pct'] = df_display['return_pct'].apply(lambda x: f"{x:.2%}")

        # Limit to recent trades
        if len(df_display) > max_trades:
            df_display = df_display.tail(max_trades)
            header = f"## Trade Log (Last {max_trades} Trades)\n"
        else:
            header = "## Trade Log (All Trades)\n"

        # Convert to markdown table
        return header + "\n" + df_display.to_markdown(index=False)

    def _generate_notes(self, notes: str) -> str:
        """Generate notes section."""
        return f"""## Notes

{notes}
"""

    def _generate_footer(self) -> str:
        """Generate report footer."""
        return f"""---

*Report generated by Backtesting System on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    # Helper methods for interpretation

    def _interpret_profit_factor(self, pf: float) -> str:
        if pf >= 2.0:
            return "Excellent (>2.0) - Strong profitability"
        elif pf >= 1.5:
            return "Good (1.5-2.0) - Solid profitability"
        elif pf >= 1.0:
            return "Acceptable (1.0-1.5) - Marginally profitable"
        else:
            return "Poor (<1.0) - Unprofitable"

    def _interpret_win_rate(self, wr: float) -> str:
        if wr >= 0.60:
            return "High (>60%) - Consistent winner selection"
        elif wr >= 0.50:
            return "Good (50-60%) - Balanced approach"
        elif wr >= 0.40:
            return "Acceptable (40-50%) - Relies on larger wins"
        else:
            return "Low (<40%) - Needs larger wins to compensate"

    def _interpret_win_loss_ratio(self, avg_win: float, avg_loss: float) -> str:
        if avg_loss == 0:
            return "N/A - No losses"
        ratio = abs(avg_win / avg_loss)
        if ratio >= 2.0:
            return f"{ratio:.2f} - Excellent risk/reward"
        elif ratio >= 1.5:
            return f"{ratio:.2f} - Good risk/reward"
        elif ratio >= 1.0:
            return f"{ratio:.2f} - Acceptable risk/reward"
        else:
            return f"{ratio:.2f} - Poor risk/reward"

    def _interpret_drawdown(self, dd: float) -> str:
        dd_pct = abs(dd) * 100
        if dd_pct < 10:
            return "low risk tolerance required"
        elif dd_pct < 20:
            return "moderate risk tolerance required"
        elif dd_pct < 30:
            return "high risk tolerance required"
        else:
            return "very high risk - may be difficult to stomach"

    def _interpret_volatility(self, vol: float) -> str:
        vol_pct = vol * 100
        if vol_pct < 15:
            return "relatively low"
        elif vol_pct < 25:
            return "moderate"
        elif vol_pct < 40:
            return "high"
        else:
            return "very high"

    def _interpret_sharpe(self, sharpe: float) -> str:
        if sharpe >= 2.0:
            return "excellent risk-adjusted returns"
        elif sharpe >= 1.0:
            return "good risk-adjusted returns"
        elif sharpe >= 0.5:
            return "acceptable risk-adjusted returns"
        else:
            return "poor risk-adjusted returns"

    def _risk_status(self, value: float, good_threshold: float,
                     bad_threshold: float, reverse: bool = False) -> str:
        if reverse:
            if value <= good_threshold:
                return "🟢 Low"
            elif value <= bad_threshold:
                return "🟡 Medium"
            else:
                return "🔴 High"
        else:
            if value >= good_threshold:
                return "🟢 Low"
            elif value >= bad_threshold:
                return "🟡 Medium"
            else:
                return "🔴 High"

    def _generate_risk_recommendations(self, max_dd: float, sharpe: float,
                                      volatility: float) -> str:
        recommendations = []

        if abs(max_dd) > 0.25:
            recommendations.append("- Consider reducing position sizes to limit drawdown")

        if sharpe < 1.0:
            recommendations.append("- Strategy may benefit from better entry/exit timing")
            recommendations.append("- Consider adding risk management rules")

        if volatility > 0.30:
            recommendations.append("- High volatility suggests need for position size adjustment")
            recommendations.append("- Consider volatility-adjusted position sizing")

        if not recommendations:
            recommendations.append("- Risk profile is acceptable for the strategy type")
            recommendations.append("- Continue monitoring performance in live trading")

        return '\n'.join(recommendations)


if __name__ == '__main__':
    # Example usage
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
        entry_date = dates[i * 8]
        exit_date = dates[min(i * 8 + 5, 251)]
        trades.append({
            'symbol': 'AAPL' if i % 2 == 0 else 'MSFT',
            'entry_time': entry_date,
            'exit_time': exit_date,
            'entry_price': 150.0 + np.random.randn() * 5,
            'exit_price': 150.0 + trade_return * 150,
            'quantity': 100,
            'pnl': trade_return * 15000,
            'return_pct': trade_return,
        })

    # Calculate metrics
    from analytics import PerformanceMetrics
    metrics_calc = PerformanceMetrics(risk_free_rate=0.02)
    metrics = metrics_calc.calculate_all(equity_curve, trades=trades)

    # Generate report
    generator = MarkdownReportGenerator(output_dir='docs/reports')

    config = {
        'initial_capital': 100000,
        'risk_per_trade': 0.02,
        'position_sizing': 'percent_equity',
        'commission': 0.001,
        'slippage': 0.0005,
    }

    notes = """
    This is a test backtest of a MACD crossover strategy.

    Key observations:
    - Strategy performs well in trending markets
    - Some false signals in ranging conditions
    - Consider adding volume filter
    """

    report_path = generator.generate_report(
        strategy_name='MACD_Strategy',
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics,
        config=config,
        notes=notes
    )

    print(f"\n✓ Report generated: {report_path}")
    print(f"✓ Charts saved to: {generator.charts_dir}")
