"""
Visualization tools for backtesting results.

Create charts and plots for equity curves, drawdowns, returns distribution, etc.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from scipy import stats
import seaborn as sns


class BacktestVisualizer:
    """
    Create visualizations for backtest results.
    """

    def __init__(self, style: str = 'seaborn-v0_8-darkgrid'):
        """
        Initialize visualizer.

        Args:
            style: Matplotlib style to use
        """
        try:
            plt.style.use(style)
        except:
            plt.style.use('default')

        # Set default figure size
        self.figsize = (12, 6)
        self.color_profit = '#2ecc71'  # Green
        self.color_loss = '#e74c3c'    # Red
        self.color_equity = '#3498db'  # Blue

    def plot_equity_curve(
        self,
        equity_curve: pd.Series,
        benchmark: Optional[pd.Series] = None,
        title: str = "Equity Curve",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Plot equity curve over time.

        Args:
            equity_curve: Time series of portfolio value
            benchmark: Optional benchmark series for comparison
            title: Chart title
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        # Plot equity curve
        ax.plot(equity_curve.index, equity_curve.values,
                label='Strategy', color=self.color_equity, linewidth=2)

        # Plot benchmark if provided
        if benchmark is not None:
            # Normalize benchmark to same starting value
            normalized_benchmark = benchmark / benchmark.iloc[0] * equity_curve.iloc[0]
            ax.plot(benchmark.index, normalized_benchmark.values,
                    label='Benchmark', color='gray', linewidth=1.5, linestyle='--')

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Value ($)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # Format x-axis dates
        if isinstance(equity_curve.index, pd.DatetimeIndex):
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=45)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def plot_drawdown(
        self,
        equity_curve: pd.Series,
        title: str = "Drawdown Over Time",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Plot drawdown over time.

        Args:
            equity_curve: Time series of portfolio value
            title: Chart title
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        # Calculate drawdown
        cummax = equity_curve.expanding().max()
        drawdown = (equity_curve - cummax) / cummax

        fig, ax = plt.subplots(figsize=self.figsize)

        # Plot drawdown
        ax.fill_between(drawdown.index, drawdown.values, 0,
                        color=self.color_loss, alpha=0.3, label='Drawdown')
        ax.plot(drawdown.index, drawdown.values, color=self.color_loss, linewidth=1.5)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        # Format y-axis as percentage
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x*100:.1f}%'))

        # Format x-axis dates
        if isinstance(equity_curve.index, pd.DatetimeIndex):
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=45)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def plot_returns_distribution(
        self,
        returns: pd.Series,
        title: str = "Returns Distribution",
        bins: int = 50,
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Plot distribution of returns.

        Args:
            returns: Series of period returns
            title: Chart title
            bins: Number of histogram bins
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Histogram
        ax1.hist(returns.values, bins=bins, color=self.color_equity,
                alpha=0.7, edgecolor='black')
        ax1.axvline(returns.mean(), color=self.color_profit, linestyle='--',
                   linewidth=2, label=f'Mean: {returns.mean():.4f}')
        ax1.axvline(returns.median(), color='orange', linestyle='--',
                   linewidth=2, label=f'Median: {returns.median():.4f}')
        ax1.set_xlabel('Returns', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title('Histogram', fontsize=12, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Q-Q plot
        stats.probplot(returns, dist="norm", plot=ax2)
        ax2.set_title('Q-Q Plot (Normal Distribution)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)

        fig.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def plot_monthly_returns(
        self,
        returns: pd.Series,
        title: str = "Monthly Returns Heatmap",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Plot monthly returns as a heatmap.

        Args:
            returns: Daily returns series with DatetimeIndex
            title: Chart title
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        # Calculate monthly returns
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)

        # Create pivot table: rows=years, columns=months
        monthly_returns_df = pd.DataFrame({
            'Year': monthly_returns.index.year,
            'Month': monthly_returns.index.month,
            'Return': monthly_returns.values
        })

        pivot = monthly_returns_df.pivot(index='Year', columns='Month', values='Return')

        # Create heatmap
        fig, ax = plt.subplots(figsize=(14, 8))

        sns.heatmap(pivot * 100, annot=True, fmt='.2f', cmap='RdYlGn',
                   center=0, cbar_kws={'label': 'Return (%)'},
                   linewidths=0.5, ax=ax)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Year', fontsize=12)

        # Set month names
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        ax.set_xticklabels(month_names)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def plot_trade_analysis(
        self,
        trades: List[Dict],
        title: str = "Trade Analysis",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Plot trade analysis including PnL distribution and cumulative PnL.

        Args:
            trades: List of trade dictionaries with 'pnl', 'exit_time', etc.
            title: Chart title
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        if not trades:
            raise ValueError("No trades to plot")

        df = pd.DataFrame(trades)

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Cumulative PnL
        df['cumulative_pnl'] = df['pnl'].cumsum()
        ax1.plot(range(len(df)), df['cumulative_pnl'].values,
                color=self.color_equity, linewidth=2)
        ax1.fill_between(range(len(df)), df['cumulative_pnl'].values, 0,
                        alpha=0.3, color=self.color_equity)
        ax1.set_xlabel('Trade Number', fontsize=12)
        ax1.set_ylabel('Cumulative P&L ($)', fontsize=12)
        ax1.set_title('Cumulative P&L', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # 2. PnL per trade
        colors = [self.color_profit if x > 0 else self.color_loss for x in df['pnl']]
        ax2.bar(range(len(df)), df['pnl'].values, color=colors, alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_xlabel('Trade Number', fontsize=12)
        ax2.set_ylabel('P&L per Trade ($)', fontsize=12)
        ax2.set_title('P&L per Trade', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)

        # 3. PnL distribution
        ax3.hist(df['pnl'].values, bins=30, color=self.color_equity,
                alpha=0.7, edgecolor='black')
        ax3.axvline(df['pnl'].mean(), color=self.color_profit, linestyle='--',
                   linewidth=2, label=f'Mean: ${df["pnl"].mean():.2f}')
        ax3.set_xlabel('P&L ($)', fontsize=12)
        ax3.set_ylabel('Frequency', fontsize=12)
        ax3.set_title('P&L Distribution', fontsize=12, fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. Win/Loss pie chart
        wins = len(df[df['pnl'] > 0])
        losses = len(df[df['pnl'] < 0])
        breakeven = len(df[df['pnl'] == 0])

        sizes = [wins, losses]
        labels = [f'Wins ({wins})', f'Losses ({losses})']
        colors_pie = [self.color_profit, self.color_loss]

        if breakeven > 0:
            sizes.append(breakeven)
            labels.append(f'Breakeven ({breakeven})')
            colors_pie.append('gray')

        ax4.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.1f%%',
               startangle=90)
        ax4.set_title('Win/Loss Distribution', fontsize=12, fontweight='bold')

        fig.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def plot_rolling_metrics(
        self,
        returns: pd.Series,
        window: int = 30,
        title: str = "Rolling Performance Metrics",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Plot rolling Sharpe ratio and volatility.

        Args:
            returns: Daily returns series
            window: Rolling window size (default 30 days)
            title: Chart title
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        # Calculate rolling metrics
        rolling_sharpe = returns.rolling(window).mean() / returns.rolling(window).std() * np.sqrt(252)
        rolling_vol = returns.rolling(window).std() * np.sqrt(252)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # Rolling Sharpe
        ax1.plot(rolling_sharpe.index, rolling_sharpe.values,
                color=self.color_equity, linewidth=1.5)
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=1)
        ax1.set_ylabel('Sharpe Ratio', fontsize=12)
        ax1.set_title(f'Rolling Sharpe Ratio ({window}-day)', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # Rolling Volatility
        ax2.plot(rolling_vol.index, rolling_vol.values,
                color=self.color_loss, linewidth=1.5)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Volatility', fontsize=12)
        ax2.set_title(f'Rolling Volatility ({window}-day)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x*100:.1f}%'))

        # Format x-axis
        if isinstance(returns.index, pd.DatetimeIndex):
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=45)

        fig.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def create_tearsheet(
        self,
        equity_curve: pd.Series,
        trades: List[Dict],
        metrics: Dict,
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Create a comprehensive tearsheet with multiple charts.

        Args:
            equity_curve: Time series of portfolio value
            trades: List of trade dictionaries
            metrics: Dictionary of performance metrics
            save_path: Optional path to save figure

        Returns:
            matplotlib Figure object
        """
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

        # 1. Equity Curve
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(equity_curve.index, equity_curve.values,
                color=self.color_equity, linewidth=2)
        ax1.set_title('Equity Curve', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Portfolio Value ($)', fontsize=10)
        ax1.grid(True, alpha=0.3)
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # 2. Drawdown
        ax2 = fig.add_subplot(gs[1, :])
        cummax = equity_curve.expanding().max()
        drawdown = (equity_curve - cummax) / cummax
        ax2.fill_between(drawdown.index, drawdown.values, 0,
                        color=self.color_loss, alpha=0.3)
        ax2.plot(drawdown.index, drawdown.values, color=self.color_loss, linewidth=1.5)
        ax2.set_title('Drawdown', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Drawdown (%)', fontsize=10)
        ax2.grid(True, alpha=0.3)
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x*100:.1f}%'))

        # 3. Returns Distribution
        ax3 = fig.add_subplot(gs[2, 0])
        returns = equity_curve.pct_change().dropna()
        ax3.hist(returns.values, bins=40, color=self.color_equity,
                alpha=0.7, edgecolor='black')
        ax3.set_title('Returns Distribution', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Returns', fontsize=10)
        ax3.set_ylabel('Frequency', fontsize=10)
        ax3.grid(True, alpha=0.3)

        # 4. Metrics Table
        ax4 = fig.add_subplot(gs[2, 1])
        ax4.axis('off')

        # Format key metrics
        metrics_text = f"""
        Total Return: {metrics.get('total_return', 0):.2%}
        CAGR: {metrics.get('cagr', 0):.2%}
        Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}
        Max Drawdown: {metrics.get('max_drawdown', 0):.2%}

        Total Trades: {metrics.get('total_trades', 0):.0f}
        Win Rate: {metrics.get('win_rate', 0):.2%}
        Profit Factor: {metrics.get('profit_factor', 0):.2f}
        Avg Win: ${metrics.get('avg_win', 0):.2f}
        Avg Loss: ${metrics.get('avg_loss', 0):.2f}
        """

        ax4.text(0.1, 0.9, 'Key Metrics', fontsize=14, fontweight='bold',
                verticalalignment='top')
        ax4.text(0.1, 0.75, metrics_text, fontsize=10,
                verticalalignment='top', family='monospace')

        fig.suptitle('Backtest Performance Tearsheet', fontsize=16, fontweight='bold')

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig


if __name__ == '__main__':
    # Example usage
    print("=" * 70)
    print("Backtest Visualizer Example")
    print("=" * 70)

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    returns = np.random.normal(0.0005, 0.01, 252)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    equity_curve = pd.Series(equity.values, index=dates)
    returns_series = pd.Series(returns, index=dates)

    # Sample trades
    trades = []
    for i in range(50):
        trade_return = np.random.normal(0.02, 0.05)
        trades.append({
            'pnl': trade_return * 10000,
            'return': trade_return,
            'exit_time': dates[i * 5]
        })

    # Create visualizer
    viz = BacktestVisualizer()

    # Plot equity curve
    print("\nPlotting equity curve...")
    viz.plot_equity_curve(equity_curve)

    # Plot drawdown
    print("Plotting drawdown...")
    viz.plot_drawdown(equity_curve)

    # Plot trade analysis
    print("Plotting trade analysis...")
    viz.plot_trade_analysis(trades)

    print("\nVisualization complete. Close the plot windows to exit.")
    plt.show()
