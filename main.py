"""
Main backtesting script.

Runs a complete backtest with:
- Data loading and preprocessing
- Strategy execution
- Performance analysis
- Report generation
"""
import os
import sys
import pandas as pd
import logging
from dotenv import load_dotenv
from pathlib import Path

from strategy.macd_strategy import MACDStrategy
from gateway.historical_gateway import HistoricalGateway
from orders.order_manager import OrderManager
from orders.order_book import OrderBook
from orders.matching_engine import RandomMatchingEngine
from portfolio import Portfolio
from backtester import (
    ExecutionEngine,
    PositionSizer,
    BacktestRecorder,
    TransactionCostCalculator,
    PercentageCommission,
    PercentageSlippage
)
from analytics import (
    PerformanceMetrics,
    BacktestAnalyzer,
    BacktestVisualizer,
    MarkdownReportGenerator
)

# Load global env
load_dotenv()
YF_DATA_PATH = Path(os.getenv("YF_TICK_PATH"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_backtest(
    symbol: str = 'AAPL',
    initial_capital: float = 100_000,
    position_sizing_method: str = 'percent_equity',
    equity_percent: float = 0.10,
    risk_per_trade: float = 0.02,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
):
    """
    Run a complete backtest.

    Args:
        symbol: Stock symbol to backtest
        initial_capital: Starting capital
        position_sizing_method: Method for position sizing
        equity_percent: Percentage of equity per position (for percent_equity method)
        risk_per_trade: Risk per trade (for risk_based method)
        commission_pct: Commission as decimal (0.001 = 0.1%)
        slippage_pct: Slippage as decimal (0.0005 = 0.05% or 5 bps)

    Returns:
        Dictionary with backtest results
    """
    logger.info("=" * 70)
    logger.info("STARTING BACKTEST")
    logger.info("=" * 70)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info(f"Position Sizing: {position_sizing_method}")
    logger.info(f"Commission: {commission_pct:.3%}")
    logger.info(f"Slippage: {slippage_pct:.3%}")
    logger.info("=" * 70)

    # 1. Initialize Strategy
    logger.info("\n[1/7] Initializing strategy...")
    strategy = MACDStrategy(
        data_path=YF_DATA_PATH,
        fast_period=12,
        slow_period=26,
        signal_period=9
    )

    # 2. Load data and create gateway
    logger.info("[2/7] Loading data...")
    df = strategy.get_data(symbol)
    logger.info(f"  Loaded {len(df)} data points from {df.index[0]} to {df.index[-1]}")

    gateway = HistoricalGateway(YF_DATA_PATH, symbol)

    # 3. Initialize components
    logger.info("[3/7] Initializing trading components...")

    # Portfolio
    portfolio = Portfolio(init_capital=initial_capital)

    # Order Manager
    order_manager = OrderManager(
        max_order_size=10000,
        max_position=20000
    )

    # Order Book
    order_book = OrderBook()

    # Matching Engine
    matching_engine = RandomMatchingEngine()

    # Position Sizer
    position_sizer = PositionSizer(
        sizing_method=position_sizing_method,
        equity_percent=equity_percent,
        risk_per_trade=risk_per_trade,
        fixed_quantity=100
    )
    logger.info(f"  Position Sizer: {position_sizing_method}")

    # Transaction Costs
    commission_model = PercentageCommission(commission_pct=commission_pct)
    slippage_model = PercentageSlippage(slippage_pct=slippage_pct)
    cost_calculator = TransactionCostCalculator(commission_model, slippage_model)
    logger.info(f"  Commission: {commission_pct:.3%}, Slippage: {slippage_pct:.3%}")

    # Recorder
    recorder = BacktestRecorder()

    # 4. Create Execution Engine
    logger.info("[4/7] Creating execution engine...")
    engine = ExecutionEngine(
        init_capital=initial_capital,
        gateway=gateway,
        strategy=strategy,
        manager=order_manager,
        book=order_book,
        matching=matching_engine,
        position_sizer=position_sizer
    )

    # 5. Run Backtest
    logger.info("[5/7] Running backtest...")
    try:
        # Note: This is a simplified run - ideally integrate recorder into execution engine
        engine.run()
        logger.info("✓ Backtest completed successfully")
    except Exception as e:
        logger.error(f"✗ Backtest failed: {e}")
        raise

    # 6. Collect Results
    logger.info("[6/7] Collecting results...")

    # Get equity curve from portfolio history
    # For now, create a simple equity curve from final value
    # TODO: Track equity at each step in ExecutionEngine
    final_value = portfolio.get_total_value()
    logger.info(f"  Initial Capital: ${initial_capital:,.2f}")
    logger.info(f"  Final Value: ${final_value:,.2f}")
    logger.info(f"  Total Return: {(final_value/initial_capital - 1):.2%}")

    # Get positions
    positions = portfolio.get_positions()
    logger.info(f"  Final Positions: {len(positions)}")
    for pos in positions:
        if pos['symbol'] != 'cash' and pos['quantity'] != 0:
            logger.info(f"    {pos['symbol']}: {pos['quantity']} @ ${pos['price']:.2f}")

    # Create a simple equity curve for now
    # In production, ExecutionEngine should track this at each step
    equity_curve = pd.Series([initial_capital, final_value], index=[df.index[0], df.index[-1]])

    # Get trade reports from engine
    trade_reports = engine.reports
    logger.info(f"  Total Order Reports: {len(trade_reports)}")

    # Convert reports to trades format for analysis
    # This is simplified - in production, track complete trade lifecycle
    trades = []

    results = {
        'strategy_name': f'MACD_{symbol}',
        'symbol': symbol,
        'initial_capital': initial_capital,
        'final_value': final_value,
        'equity_curve': equity_curve,
        'trades': trades,
        'positions': positions,
        'reports': trade_reports,
        'config': {
            'symbol': symbol,
            'initial_capital': initial_capital,
            'position_sizing': position_sizing_method,
            'equity_percent': equity_percent,
            'risk_per_trade': risk_per_trade,
            'commission_pct': commission_pct,
            'slippage_pct': slippage_pct,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
        }
    }

    return results


def analyze_results(results: dict):
    """
    Analyze backtest results and generate report.

    Args:
        results: Dictionary with backtest results
    """
    logger.info("[7/7] Analyzing results and generating report...")

    equity_curve = results['equity_curve']
    trades = results['trades']

    # Calculate metrics
    logger.info("\nCalculating performance metrics...")
    metrics_calc = PerformanceMetrics(risk_free_rate=0.02)

    # For now, with limited data, calculate basic metrics
    total_return = (results['final_value'] / results['initial_capital']) - 1

    metrics = {
        'total_return': total_return,
        'cagr': 0.0,  # Need full equity curve
        'annualized_return': 0.0,
        'volatility': 0.0,
        'sharpe_ratio': 0.0,
        'sortino_ratio': 0.0,
        'max_drawdown': 0.0,
        'max_drawdown_duration': 0,
        'calmar_ratio': 0.0,
        'best_day': 0.0,
        'worst_day': 0.0,
        'positive_days': 0,
        'negative_days': 0,
        'win_rate_daily': 0.0,
        'total_trades': len(trades),
        'winning_trades': len([t for t in trades if t.get('pnl', 0) > 0]),
        'losing_trades': len([t for t in trades if t.get('pnl', 0) < 0]),
        'win_rate': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'profit_factor': 0.0,
        'largest_win': 0.0,
        'largest_loss': 0.0,
        'avg_trade_pnl': 0.0,
        'gross_profit': 0.0,
        'gross_loss': 0.0,
    }

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("BACKTEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Strategy: {results['strategy_name']}")
    logger.info(f"Symbol: {results['symbol']}")
    logger.info(f"\nPerformance:")
    logger.info(f"  Initial Capital: ${results['initial_capital']:,.2f}")
    logger.info(f"  Final Value:     ${results['final_value']:,.2f}")
    logger.info(f"  Total Return:    {metrics['total_return']:.2%}")
    logger.info(f"\nTrades:")
    logger.info(f"  Total Orders:    {len(results['reports'])}")
    logger.info(f"  Completed Trades: {len(trades)}")
    logger.info(f"\nPositions:")
    for pos in results['positions']:
        if pos['symbol'] != 'cash':
            logger.info(f"  {pos['symbol']}: {pos['quantity']:.0f} shares @ ${pos['price']:.2f} = ${pos['quantity'] * pos['price']:,.2f}")

    # Generate markdown report
    logger.info("\n" + "=" * 70)
    logger.info("GENERATING MARKDOWN REPORT")
    logger.info("=" * 70)

    notes = f"""
## Backtest Details

This backtest ran the MACD crossover strategy on {results['symbol']}.

### Strategy Logic
- **Entry Signal:** MACD crosses above signal line (bullish)
- **Exit Signal:** MACD crosses below signal line (bearish)
- **Position Sizing:** {results['config']['position_sizing']}

### Observations
- The strategy generated {len(results['reports'])} order events
- Final portfolio value: ${results['final_value']:,.2f}
- Total return: {metrics['total_return']:.2%}

### Next Steps
- Review individual trades for patterns
- Consider adding filters (volume, trend strength)
- Optimize parameters (MACD periods, position sizing)
- Test on different market conditions
"""

    # Note: Report generation requires full equity curve with proper timestamps
    # For now, just save a simple summary
    logger.info(f"\n✓ Backtest analysis complete")
    logger.info(f"✓ Total Return: {metrics['total_return']:.2%}")

    if len(trades) > 0:
        try:
            generator = MarkdownReportGenerator()
            report_path = generator.generate_report(
                strategy_name=results['strategy_name'],
                equity_curve=equity_curve,
                trades=trades,
                metrics=metrics,
                config=results['config'],
                notes=notes
            )
            logger.info(f"✓ Report saved to: {report_path}")
        except Exception as e:
            logger.warning(f"Could not generate full report: {e}")
            logger.info("  (This is expected if there are no completed trades)")
    else:
        logger.info("  No trades completed - skipping detailed report generation")

    logger.info("\n" + "=" * 70)

    return metrics


def main():
    """Main entry point."""
    try:
        # Run backtest
        results = run_backtest(
            symbol='AAPL',
            initial_capital=100_000,
            position_sizing_method='percent_equity',
            equity_percent=0.10,
            commission_pct=0.001,
            slippage_pct=0.0005
        )

        # Analyze results
        metrics = analyze_results(results)

        logger.info("\n✓ Backtest pipeline completed successfully!")

    except Exception as e:
        logger.error(f"\n✗ Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
