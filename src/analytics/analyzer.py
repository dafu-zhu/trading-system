"""
Backtest results analyzer.

Analyzes trades, positions, and performance to generate comprehensive reports.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from analytics.metrics import PerformanceMetrics, format_metrics


class BacktestAnalyzer:
    """
    Analyze backtest results including trades, equity curve, and positions.
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
        self.positions_history = []

    def add_trade(self, trade: Dict) -> None:
        """
        Add a completed trade to the analyzer.

        Trade dict should contain:
            - symbol: str
            - entry_time: datetime
            - exit_time: datetime
            - entry_price: float
            - exit_price: float
            - quantity: float
            - side: str ('BUY' or 'SELL')
            - pnl: float
            - return: float
        """
        self.trades.append(trade)

    def set_equity_curve(self, equity_curve: pd.Series) -> None:
        """Set the equity curve time series."""
        self.equity_curve = equity_curve

    def set_positions_history(self, positions: List[Dict]) -> None:
        """Set the positions history."""
        self.positions_history = positions

    def analyze(self) -> Dict:
        """
        Perform comprehensive analysis of backtest results.

        Returns:
            Dictionary containing all analysis results
        """
        results = {}

        # Performance metrics
        if self.equity_curve is not None:
            metrics = self.metrics_calc.calculate_all(
                self.equity_curve,
                trades=self.trades
            )
            results['metrics'] = metrics

        # Trade analysis
        if self.trades:
            results['trade_analysis'] = self._analyze_trades()

        # Position analysis
        if self.positions_history:
            results['position_analysis'] = self._analyze_positions()

        # Time-based analysis
        if self.trades:
            results['time_analysis'] = self._analyze_by_time()

        return results

    def _analyze_trades(self) -> Dict:
        """Analyze individual trades."""
        if not self.trades:
            return {}

        df = pd.DataFrame(self.trades)

        analysis = {
            'total_trades': len(df),
            'symbols_traded': df['symbol'].nunique() if 'symbol' in df else 0,
        }

        # PnL analysis
        if 'pnl' in df:
            analysis.update({
                'total_pnl': df['pnl'].sum(),
                'avg_pnl_per_trade': df['pnl'].mean(),
                'median_pnl': df['pnl'].median(),
                'pnl_std': df['pnl'].std(),
            })

            # Win/loss analysis
            wins = df[df['pnl'] > 0]
            losses = df[df['pnl'] < 0]
            breakeven = df[df['pnl'] == 0]

            analysis.update({
                'winning_trades': len(wins),
                'losing_trades': len(losses),
                'breakeven_trades': len(breakeven),
                'win_rate': len(wins) / len(df) if len(df) > 0 else 0,
                'avg_win': wins['pnl'].mean() if len(wins) > 0 else 0,
                'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0,
                'largest_win': df['pnl'].max(),
                'largest_loss': df['pnl'].min(),
                'best_trade': df.loc[df['pnl'].idxmax()].to_dict() if len(df) > 0 else {},
                'worst_trade': df.loc[df['pnl'].idxmin()].to_dict() if len(df) > 0 else {},
            })

            # Profit factor
            gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
            gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
            analysis['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else 0

        # Trade duration analysis
        if 'entry_time' in df and 'exit_time' in df:
            df['duration'] = pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])
            analysis.update({
                'avg_trade_duration': df['duration'].mean(),
                'median_trade_duration': df['duration'].median(),
                'min_duration': df['duration'].min(),
                'max_duration': df['duration'].max(),
            })

        # Return analysis
        if 'return' in df:
            analysis.update({
                'avg_return': df['return'].mean(),
                'median_return': df['return'].median(),
                'return_std': df['return'].std(),
            })

        # Per-symbol analysis
        if 'symbol' in df and 'pnl' in df:
            by_symbol = df.groupby('symbol')['pnl'].agg(['count', 'sum', 'mean'])
            by_symbol.columns = ['trades', 'total_pnl', 'avg_pnl']
            analysis['by_symbol'] = by_symbol.to_dict('index')

        return analysis

    def _analyze_positions(self) -> Dict:
        """Analyze position history."""
        if not self.positions_history:
            return {}

        df = pd.DataFrame(self.positions_history)

        analysis = {
            'total_positions': len(df),
        }

        if 'quantity' in df:
            analysis.update({
                'avg_position_size': df['quantity'].mean(),
                'max_position_size': df['quantity'].max(),
                'min_position_size': df['quantity'].min(),
            })

        if 'value' in df:
            analysis.update({
                'avg_position_value': df['value'].mean(),
                'max_position_value': df['value'].max(),
                'total_position_value': df['value'].sum(),
            })

        return analysis

    def _analyze_by_time(self) -> Dict:
        """Analyze trades by time periods."""
        if not self.trades:
            return {}

        df = pd.DataFrame(self.trades)

        if 'exit_time' not in df or 'pnl' not in df:
            return {}

        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df = df.set_index('exit_time')

        analysis = {}

        # Monthly performance
        monthly = df['pnl'].resample('ME').agg(['sum', 'count', 'mean'])
        monthly.columns = ['pnl', 'trades', 'avg_pnl']
        analysis['monthly'] = monthly.to_dict('index')

        # Weekly performance
        weekly = df['pnl'].resample('W').sum()
        analysis['weekly_avg_pnl'] = weekly.mean()
        analysis['best_week'] = weekly.max()
        analysis['worst_week'] = weekly.min()

        # Day of week analysis
        df['day_of_week'] = df.index.day_name()
        by_day = df.groupby('day_of_week')['pnl'].agg(['count', 'sum', 'mean'])
        by_day.columns = ['trades', 'total_pnl', 'avg_pnl']
        analysis['by_day_of_week'] = by_day.to_dict('index')

        return analysis

    def get_trade_summary(self) -> pd.DataFrame:
        """Get summary DataFrame of all trades."""
        if not self.trades:
            return pd.DataFrame()

        df = pd.DataFrame(self.trades)

        # Sort by exit time if available
        if 'exit_time' in df:
            df = df.sort_values('exit_time')

        return df

    def get_winning_trades(self) -> pd.DataFrame:
        """Get DataFrame of winning trades."""
        df = self.get_trade_summary()
        if df.empty or 'pnl' not in df:
            return pd.DataFrame()
        return df[df['pnl'] > 0]

    def get_losing_trades(self) -> pd.DataFrame:
        """Get DataFrame of losing trades."""
        df = self.get_trade_summary()
        if df.empty or 'pnl' not in df:
            return pd.DataFrame()
        return df[df['pnl'] < 0]

    def generate_report(self) -> str:
        """
        Generate comprehensive text report of backtest results.

        Returns:
            Formatted string report
        """
        analysis = self.analyze()
        report = []

        report.append("=" * 70)
        report.append("BACKTEST ANALYSIS REPORT")
        report.append("=" * 70)

        # Performance metrics
        if 'metrics' in analysis:
            report.append("\n" + format_metrics(analysis['metrics']))

        # Trade analysis
        if 'trade_analysis' in analysis:
            ta = analysis['trade_analysis']
            report.append("\n" + "=" * 70)
            report.append("TRADE ANALYSIS")
            report.append("=" * 70)
            report.append(f"\nTotal Trades:          {ta.get('total_trades', 0):>10.0f}")
            report.append(f"Symbols Traded:        {ta.get('symbols_traded', 0):>10.0f}")

            if 'total_pnl' in ta:
                report.append(f"\nTotal P&L:             ${ta.get('total_pnl', 0):>10.2f}")
                report.append(f"Avg P&L per Trade:     ${ta.get('avg_pnl_per_trade', 0):>10.2f}")
                report.append(f"Median P&L:            ${ta.get('median_pnl', 0):>10.2f}")

            if 'avg_trade_duration' in ta:
                report.append(f"\nAvg Trade Duration:    {ta['avg_trade_duration']}")
                report.append(f"Median Duration:       {ta['median_trade_duration']}")

            if 'by_symbol' in ta:
                report.append("\nPerformance by Symbol:")
                for symbol, stats in ta['by_symbol'].items():
                    report.append(f"  {symbol:>6}: {stats['trades']:3.0f} trades, "
                                f"${stats['total_pnl']:>10.2f} total, "
                                f"${stats['avg_pnl']:>8.2f} avg")

        # Time analysis
        if 'time_analysis' in analysis:
            ta = analysis['time_analysis']
            if 'by_day_of_week' in ta:
                report.append("\n" + "=" * 70)
                report.append("PERFORMANCE BY DAY OF WEEK")
                report.append("=" * 70)
                for day, stats in ta['by_day_of_week'].items():
                    report.append(f"  {day:>9}: {stats['trades']:3.0f} trades, "
                                f"${stats['total_pnl']:>10.2f} total, "
                                f"${stats['avg_pnl']:>8.2f} avg")

        report.append("\n" + "=" * 70)
        return "\n".join(report)

    def export_to_csv(self, filepath: str) -> None:
        """Export trade summary to CSV file."""
        df = self.get_trade_summary()
        if not df.empty:
            df.to_csv(filepath, index=False)

    def export_metrics_to_dict(self) -> Dict:
        """Export all analysis as dictionary for JSON serialization."""
        analysis = self.analyze()

        # Convert non-serializable types
        result = {}
        for key, value in analysis.items():
            if isinstance(value, pd.DataFrame):
                result[key] = value.to_dict('records')
            elif isinstance(value, dict):
                result[key] = self._make_json_serializable(value)
            else:
                result[key] = value

        return result

    def _make_json_serializable(self, obj):
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timedelta):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj


if __name__ == '__main__':
    # Example usage
    print("=" * 70)
    print("Backtest Analyzer Example")
    print("=" * 70)

    # Create analyzer
    analyzer = BacktestAnalyzer(risk_free_rate=0.02)

    # Add sample trades
    trades = [
        {
            'symbol': 'AAPL',
            'entry_time': pd.Timestamp('2023-01-10'),
            'exit_time': pd.Timestamp('2023-01-15'),
            'entry_price': 150.0,
            'exit_price': 155.0,
            'quantity': 100,
            'side': 'BUY',
            'pnl': 500.0,
            'return': 0.033
        },
        {
            'symbol': 'AAPL',
            'entry_time': pd.Timestamp('2023-01-20'),
            'exit_time': pd.Timestamp('2023-01-25'),
            'entry_price': 155.0,
            'exit_price': 153.0,
            'quantity': 100,
            'side': 'BUY',
            'pnl': -200.0,
            'return': -0.013
        },
        {
            'symbol': 'MSFT',
            'entry_time': pd.Timestamp('2023-02-01'),
            'exit_time': pd.Timestamp('2023-02-10'),
            'entry_price': 250.0,
            'exit_price': 260.0,
            'quantity': 50,
            'side': 'BUY',
            'pnl': 500.0,
            'return': 0.04
        },
    ]

    for trade in trades:
        analyzer.add_trade(trade)

    # Generate sample equity curve
    dates = pd.date_range('2023-01-01', periods=60, freq='D')
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 60)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    equity_curve = pd.Series(equity.values, index=dates)
    analyzer.set_equity_curve(equity_curve)

    # Generate report
    print(analyzer.generate_report())

    # Show trade summary
    print("\nTrade Summary:")
    print(analyzer.get_trade_summary()[['symbol', 'entry_price', 'exit_price', 'pnl', 'return']])
