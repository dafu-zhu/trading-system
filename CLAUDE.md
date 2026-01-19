# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run tests (excludes integration tests by default)
uv run pytest tests/

# Run with integration tests (requires ALPACA_API_KEY)
uv run pytest tests/ -m integration

# Run single test file
uv run pytest tests/test_portfolio.py

# Run specific test
uv run pytest tests/test_portfolio.py::TestPosition::test_position_creation

# Lint (uses ruff, not black/flake8)
uv run ruff check src/
uv run ruff format src/
```

## Entry Points

```bash
# Backtest a strategy
python run_backtest.py --symbol AAPL --start 2023-01-01 --end 2024-01-01

# Paper trading
python run_paper.py

# Fetch historical data
python scripts/fetch_historical.py --symbols AAPL MSFT GOOGL
```

## Architecture Overview

This is an **event-driven backtesting system** using **Alpaca API** as the sole data source.

### Data Flow

1. **Data Fetching**: `AlpacaDataGateway` fetches bars from Alpaca API → caches in SQLite
2. **Feature Calculation**: `FeatureCalculator` calculates MACD, RSI, moving averages from bars
3. **Signal Generation**: `MACDStrategy` generates BUY/SELL/HOLD signals
4. **Execution**: `BacktestEngine` processes signals via `DeterministicMatchingEngine`
5. **Analysis**: `EquityTracker` and `TradeTracker` record performance

### Key Abstractions (src/models.py)

- `DataGateway` - Abstract data source (implement `fetch_bars()`, `stream_bars()`)
- `TradingGateway` - Abstract broker connection (implement `submit_order()`, `get_positions()`)
- `Strategy` - Abstract signal generator (implement `generate_signals(tick)`)
- `MatchingEngine` - Abstract order matcher (implement `match(order, orderbook)`)
- `PositionSizer` - Abstract position sizing (implement `calculate_qty(signal, portfolio, price)`)

### Module Structure

```
src/
├── gateway/
│   ├── alpaca_data_gateway.py   # Historical data from Alpaca
│   └── alpaca_trading_gateway.py # Paper/live trading
├── strategy/
│   └── macd_strategy.py         # MACD crossover strategy
├── backtester/
│   ├── backtest_engine.py       # Main backtest runner
│   └── execution.py             # Legacy execution engine
├── orders/
│   └── matching_engine.py       # DeterministicMatchingEngine
├── data_loader/
│   ├── storage.py               # SQLite bar storage
│   └── features/
│       └── calculator.py        # Technical indicators
├── analytics/                   # Performance metrics
└── portfolio.py                 # Portfolio management
```

### Data Storage

- **SQLite**: `data/trading.db` stores OHLCV bars
- **Schema**: `bars(symbol, timestamp, timeframe, open, high, low, close, volume)`
- **Caching**: AlpacaDataGateway caches fetched bars automatically

### Order State Machine

`NEW` → `ACKED` → `PARTIALLY_FILLED`/`FILLED`/`CANCELED`
`NEW` → `REJECTED`

## Environment Variables

```bash
# Required for Alpaca API
ALPACA_API_KEY=<your-key>
ALPACA_API_SECRET=<your-secret>
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

## Data Providers

- **Historical**: Alpaca API via `AlpacaDataGateway` (8 years of data)
- **Live Trading**: Alpaca paper trading via `AlpacaTradingGateway`
- **Supported Timeframes**: 1Min, 5Min, 15Min, 30Min, 1Hour, 4Hour, 1Day, 1Week, 1Month

## Conventions

- Python 3.13+, managed by `uv`
- Imports use package names directly (e.g., `from models import DataGateway`)
- Technical indicators use lowercase column names (`close`, `open`, `high`, `low`)
- Timestamps stored as naive UTC in SQLite
- Tests use pytest with `@pytest.mark.integration` for API tests
