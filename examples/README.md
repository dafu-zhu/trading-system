# Trading System Examples

Runnable examples for testing backtest, paper trade, and dry-run modes.

## Quick Start

```bash
# From project root
cd /Users/zdf/Documents/GitHub/trading-system

# Set environment variables (required for Alpaca API)
export ALPACA_API_KEY="your-key"
export ALPACA_API_SECRET="your-secret"
```

## Examples Overview

| Script | Asset | Mode | Strategy |
|--------|-------|------|----------|
| `stock_backtest.py` | AAPL | Backtest | MACD |
| `stock_dryrun.py` | AAPL | Dry-run | MACD |
| `crypto_backtest.py` | BTC/USD | Backtest | MACD |
| `crypto_paper.py` | BTC/USD | Paper | Momentum |
| `crypto_dryrun.py` | BTC/USD | Dry-run | Momentum |
| `alpha_backtest.py` | Multi | Backtest | Alpha |
| `run_all_tests.py` | All | All | All |

## Running Examples

```bash
# Individual examples
python examples/stock_backtest.py
python examples/crypto_backtest.py
python examples/crypto_paper.py
python examples/crypto_dryrun.py

# Run all tests
python examples/run_all_tests.py
```

## Expected Output

Each script logs:
- Configuration parameters
- Data fetching progress
- Signal generation
- Order execution
- Performance summary
