# Trading System Tutorial

A step-by-step guide to using the Alpaca-powered trading system for backtesting and paper trading.

## 1. Installation & Setup

### Prerequisites

- Python 3.13+
- uv (Python package manager)
- Alpaca account (free tier works)

### Install Dependencies

```bash
# Clone the repository
git clone <repo-url>
cd trading-system

# Install dependencies
uv sync
```

## 2. Configuration

### Create .env File

Create a `.env` file in the project root:

```bash
ALPACA_API_KEY=your_api_key_here
ALPACA_API_SECRET=your_api_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

Get your API keys from [Alpaca Dashboard](https://app.alpaca.markets/paper/dashboard/overview).

### Verify Setup

```bash
# Run tests to verify installation
uv run pytest tests/ -v
```

## 3. Fetching Historical Data

Before backtesting, fetch historical data:

```bash
# Fetch daily data for default symbols (AAPL, MSFT, GOOGL, AMZN, TSLA)
python scripts/fetch_historical.py

# Fetch specific symbols
python scripts/fetch_historical.py --symbols AAPL NVDA

# Custom date range
python scripts/fetch_historical.py --start 2020-01-01 --end 2024-01-01

# Check storage statistics
python scripts/fetch_historical.py --stats
```

Data is cached in `data/trading.db` (SQLite).

## 4. Creating a Strategy

Strategies implement the `Strategy` ABC from `models.py`.

### Example: Using MACDStrategy

```python
from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.macd_strategy import MACDStrategy
from models import Timeframe

# Connect to Alpaca
gateway = AlpacaDataGateway()
gateway.connect()

# Create strategy
strategy = MACDStrategy(
    gateway=gateway,
    timeframe=Timeframe.DAY_1,
    fast_period=12,
    slow_period=26,
    signal_period=9,
)

# Generate signals for a date range
signals_df = strategy.generate_signals_batch(
    symbol="AAPL",
    start=datetime(2023, 1, 1),
    end=datetime(2024, 1, 1),
)

print(signals_df[['close', 'macd', 'signal']].tail())
```

### Creating a Custom Strategy

```python
from models import Strategy, MarketDataPoint

class MyStrategy(Strategy):
    def __init__(self, gateway, timeframe):
        self._gateway = gateway
        self._timeframe = timeframe

    def generate_signals(self, tick: MarketDataPoint) -> list:
        # Your signal logic here
        return [{
            'action': 'BUY',  # or 'SELL' or 'HOLD'
            'timestamp': tick.timestamp,
            'symbol': tick.symbol,
            'price': tick.price,
        }]
```

## 5. Running a Backtest

### Using the CLI

```bash
# Basic backtest
python run_backtest.py --symbol AAPL

# Custom parameters
python run_backtest.py \
    --symbol MSFT \
    --start 2023-01-01 \
    --end 2024-01-01 \
    --capital 50000 \
    --position-size 0.15 \
    --slippage 5

# Verbose output with trade history
python run_backtest.py --symbol AAPL -v
```

### Programmatic Backtest

```python
from datetime import datetime
from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.macd_strategy import MACDStrategy
from backtester.backtest_engine import BacktestEngine
from models import Timeframe

# Setup
gateway = AlpacaDataGateway()
gateway.connect()

strategy = MACDStrategy(gateway=gateway, timeframe=Timeframe.DAY_1)

engine = BacktestEngine(
    gateway=gateway,
    strategy=strategy,
    init_capital=100000.0,
    slippage_bps=5.0,
)

# Run backtest
results = engine.run(
    symbol="AAPL",
    timeframe=Timeframe.DAY_1,
    start=datetime(2023, 1, 1),
    end=datetime(2024, 1, 1),
)

# Analyze results
print(f"Total Return: {results['total_return_pct']:.2f}%")
print(f"Total Trades: {results['total_trades']}")
```

## 6. Paper Trading

### Interactive Paper Trading

```bash
# Connect to Alpaca paper trading
python run_paper.py

# Available commands:
# buy AAPL 10       - Buy 10 shares of AAPL
# sell AAPL 5       - Sell 5 shares of AAPL
# info              - Show account info
# pos               - Show positions
# quit              - Exit
```

### Local Simulation Mode

```bash
# Run with local simulation (no API calls)
python run_paper.py --simulate
```

### Programmatic Paper Trading

```python
from gateway.alpaca_trading_gateway import AlpacaTradingGateway
from models import OrderSide, OrderType

# Connect
gateway = AlpacaTradingGateway()
gateway.connect()

# Check account
account = gateway.get_account()
print(f"Buying Power: ${account.buying_power:,.2f}")

# Submit order
result = gateway.submit_order(
    symbol="AAPL",
    side=OrderSide.BUY,
    quantity=10,
    order_type=OrderType.MARKET,
)
print(f"Order ID: {result.order_id}")

# Check positions
positions = gateway.get_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.quantity} shares @ ${pos.avg_entry_price:.2f}")
```

## 7. Analyzing Results

### Backtest Results Structure

```python
results = {
    'symbol': 'AAPL',
    'start': datetime(2023, 1, 1),
    'end': datetime(2024, 1, 1),
    'bar_count': 252,
    'initial_capital': 100000.0,
    'final_value': 115000.0,
    'total_return_pct': 15.0,
    'total_trades': 24,
    'equity_curve': [...],
    'trades': [...],
}
```

### Plotting Equity Curve

```python
import matplotlib.pyplot as plt

# Get equity curve from results
equity_curve = results['equity_curve']
timestamps = [e['timestamp'] for e in equity_curve]
values = [e['value'] for e in equity_curve]

plt.figure(figsize=(12, 6))
plt.plot(timestamps, values)
plt.title(f"{results['symbol']} Backtest - Return: {results['total_return_pct']:.2f}%")
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.grid(True)
plt.show()
```

## Troubleshooting

### Common Issues

1. **"API credentials required"**
   - Ensure `.env` file exists with correct API keys
   - Run `source .env` or restart your terminal

2. **"No bar data available"**
   - Run `python scripts/fetch_historical.py` first
   - Check if symbol is valid and tradeable

3. **Integration tests failing**
   - Integration tests require valid API credentials
   - Run unit tests only: `pytest tests/ -m "not integration"`

### Getting Help

- Check `CLAUDE.md` for architecture overview
- Run tests: `uv run pytest tests/ -v`
- Check logs for detailed error messages
