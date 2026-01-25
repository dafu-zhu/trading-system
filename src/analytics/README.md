# Analytics Module

Performance analysis and reporting for backtesting results.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `metrics.py` | `PerformanceMetrics` | Calculate Sharpe, max drawdown, win ratio, P&L ratio |
| `analyzer.py` | `Analyzer` | Aggregate analysis utilities |
| `report.py` | `MarkdownReportGenerator` | Generate markdown reports from results |
| `visualizer.py` | `Visualizer` | Plot equity curves and trade distributions |

## Usage

```python
from analytics import PerformanceMetrics, MarkdownReportGenerator

# Calculate metrics
metrics = PerformanceMetrics(risk_free_rate=0.02)
results = metrics.calculate_all(equity_curve, trades)

# Generate report
generator = MarkdownReportGenerator()
report_path = generator.generate_report(
    strategy_name="MACD_AAPL",
    equity_curve=equity_curve,
    trades=trades,
    config=config
)
```

## Metrics Calculated

- **Sharpe Ratio**: Risk-adjusted return (annualized)
- **Max Drawdown**: Maximum peak-to-trough decline
- **Win Ratio**: Percentage of profitable trades
- **Profit/Loss Ratio**: Average win / average loss
