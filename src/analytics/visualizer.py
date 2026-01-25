"""
Simplified visualization for backtesting results.

Creates a single essential chart: PnL curve by ticks.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Optional


class BacktestVisualizer:
    """
    Create PnL curve visualization for backtest results.
    """

    def __init__(self):
        """Initialize visualizer with default styling."""
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except OSError:
            plt.style.use('default')

        self.figsize = (12, 6)
        self.color_pnl = '#3498db'  # Blue

    def plot_pnl_curve(
        self,
        equity_curve: pd.Series,
        title: str = "Portfolio Value Over Time",
        save_path: Optional[str] = None,
        show: bool = False
    ) -> plt.Figure:
        """
        Plot PnL curve by ticks.

        Args:
            equity_curve: Time series of portfolio value indexed by timestamp
            title: Chart title
            save_path: Optional path to save figure
            show: Whether to display the plot

        Returns:
            matplotlib Figure object
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        # Plot equity curve
        ax.plot(equity_curve.index, equity_curve.values,
                label='Portfolio Value', color=self.color_pnl, linewidth=2)

        # Add horizontal line at initial value for reference
        initial_value = equity_curve.iloc[0]
        ax.axhline(y=initial_value, color='gray', linestyle='--',
                   linewidth=1, alpha=0.7, label=f'Initial: ${initial_value:,.0f}')

        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Portfolio Value ($)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # Format x-axis based on index type
        if isinstance(equity_curve.index, pd.DatetimeIndex):
            # Determine appropriate date format based on time range
            time_range = (equity_curve.index[-1] - equity_curve.index[0]).days

            if time_range > 365:
                # More than a year: show year-month
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            elif time_range > 30:
                # More than a month: show month-day
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            else:
                # Less than a month: show month-day hour
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))

            plt.xticks(rotation=45)
        else:
            # If not datetime index, just use tick number
            ax.set_xlabel('Tick Number', fontsize=12)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        if show:
            plt.show()

        return fig


if __name__ == '__main__':
    import numpy as np

    print("=" * 70)
    print("Backtest Visualizer Example")
    print("=" * 70)

    # Generate sample equity curve
    np.random.seed(42)
    dates = pd.date_range('2023-01-01 09:30', periods=252, freq='30min')
    returns = np.random.normal(0.0005, 0.01, 252)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    equity_curve = pd.Series(equity.values, index=dates)

    print(f"\nGenerated equity curve with {len(equity_curve)} ticks")
    print(f"Initial value: ${equity_curve.iloc[0]:,.2f}")
    print(f"Final value: ${equity_curve.iloc[-1]:,.2f}")
    print(f"Total return: {(equity_curve.iloc[-1]/equity_curve.iloc[0] - 1):.2%}")

    # Create visualizer
    viz = BacktestVisualizer()

    # Plot PnL curve
    print("\nPlotting PnL curve...")
    viz.plot_pnl_curve(equity_curve, show=True)

    print("\nVisualization complete.")
