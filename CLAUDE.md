# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run tests (integration tests excluded by default via conftest)
uv run pytest tests/

# Include integration tests (requires ALPACA_API_KEY, ALPACA_API_SECRET)
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
# Backtest a strategy (defaults: AAPL, last year, 1Day bars, $100k, 10% position size)
python run_backtest.py --symbol AAPL --start 2023-01-01 --end 2024-01-01

# With custom parameters
python run_backtest.py --symbol MSFT --timeframe 1Hour --capital 50000 --position-size 0.05 --slippage 10 -v

# Live trading - dry run (historical data replay, no API)
python run_live.py --symbols AAPL,MSFT --dry-run --replay-days 5

# Live trading - paper mode (real-time data, simulated orders)
python run_live.py --symbols AAPL,MSFT --paper

# Live trading - with config file
python run_live.py --symbols AAPL --config config/live_trading.yaml --paper

# Legacy paper trading
python run_paper.py

# Fetch historical data
python scripts/fetch_historical.py --symbols AAPL MSFT GOOGL
```

## Architecture Overview

This is an **event-driven backtesting system** using **Alpaca API** as the sole data source.

### Data Flow

1. **Data Fetching**: `AlpacaDataGateway` fetches bars from Alpaca API → caches in SQLite
2. **Feature Calculation**: `FeatureCalculator` (in `data_loader/features/calculator.py`) calculates MACD, RSI, Bollinger Bands, ATR, moving averages from bars → returns enriched DataFrame
3. **Signal Generation**: `MACDStrategy` uses `FeatureCalculator` internally, generates BUY/SELL/HOLD signals based on MACD crossovers
4. **Position Sizing**: `PercentSizer` calculates order quantity as % of portfolio equity (default 10%)
5. **Execution**: `BacktestEngine` processes signals via `DeterministicMatchingEngine` (fills at close price, respects volume limits, applies slippage)
6. **Analysis**: `EquityTracker` and `TradeTracker` record performance

### Key Abstractions (src/models.py)

- `DataGateway` - Abstract data source (implement `fetch_bars()`, `stream_bars()`, `get_latest_bar()`)
- `TradingGateway` - Abstract broker connection (implement `submit_order()`, `cancel_order()`, `get_positions()`)
- `Strategy` - Abstract signal generator (implement `generate_signals(tick: MarketDataPoint) -> list`)
- `MatchingEngine` - Abstract order matcher (implement `match(order, orderbook) -> dict`)
- `PositionSizer` - Abstract position sizing (implement `calculate_qty(signal, portfolio, price) -> int`)

### Module Structure

```
src/
├── models.py                    # Core abstractions and data classes (Bar, Order types, enums)
├── portfolio.py                 # Portfolio/Position management (composite pattern)
├── gateway/
│   ├── alpaca_data_gateway.py   # Historical data from Alpaca (implements DataGateway)
│   ├── alpaca_trading_gateway.py # Paper/live trading (implements TradingGateway)
│   └── order_gateway.py         # CSV audit logging for order lifecycle events
├── strategy/
│   └── macd_strategy.py         # MACD crossover strategy (implements Strategy)
├── backtester/
│   ├── backtest_engine.py       # Main backtest runner
│   ├── position_sizer.py        # PercentSizer, FixedSizer, KellySizer, VolatilitySizer
│   ├── equity_tracker.py        # Tracks portfolio value over time
│   └── trade_tracker.py         # Records completed trades
├── orders/
│   ├── matching_engine.py       # DeterministicMatchingEngine (implements MatchingEngine)
│   ├── order.py                 # Order class with state machine
│   ├── order_manager.py         # Order validation
│   ├── order_book.py            # Order book structure
│   └── order_validator.py       # Rate limiting, capital checks, position limits
├── config/
│   └── trading_config.py        # TradingConfig, RiskConfig, StopLossConfig, LiveEngineConfig
├── risk/
│   └── risk_manager.py          # Stop-loss, trailing stops, circuit breaker
├── live/
│   └── live_engine.py           # Real-time trading orchestration engine
├── data_loader/
│   ├── storage.py               # SQLite bar storage
│   └── features/
│       └── calculator.py        # Technical indicators (MACD, RSI, BB, ATR, MA)
└── analytics/                   # Performance metrics and visualization
```

### Data Storage

- **SQLite**: `data/trading.db` stores OHLCV bars
- **Schema**: `bars(symbol, timestamp, timeframe, open, high, low, close, volume)`
- **Caching**: AlpacaDataGateway caches fetched bars automatically

### Order State Machine

```
NEW → ACKED → PARTIALLY_FILLED → FILLED
         ↓          ↓
      CANCELED   CANCELED
NEW → REJECTED
```

Orders must be in `ACKED` state before matching engine processes them.

## Environment Variables

```bash
# Required for Alpaca API
ALPACA_API_KEY=<your-key>
ALPACA_API_SECRET=<your-secret>
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Live trading configuration (optional, see deploy/.env.example for full list)
TRADING_DRY_RUN=true          # true = simulate orders
TRADING_ENABLE=true           # false = monitoring only
TRADING_PAPER_MODE=true       # false = REAL MONEY (use with caution)
```

## Data Providers

- **Historical**: Alpaca API via `AlpacaDataGateway` (8 years of data)
- **Live Trading**: Alpaca paper trading via `AlpacaTradingGateway`
- **Supported Timeframes**: 1Min, 5Min, 15Min, 30Min, 1Hour, 4Hour, 1Day, 1Week, 1Month

### DeterministicMatchingEngine Behavior

- Fills market orders at bar close (configurable: `fill_at="open"`, `"vwap"`, `"close"`)
- Respects volume limits: max fill = `bar.volume * max_volume_pct` (default 10%)
- Slippage: buy orders get worse (higher) price, sell orders get worse (lower) price
- Limit orders fill if limit price within bar's [low, high] range

## Conventions

- Python 3.13+, managed by `uv`
- Imports use package names directly (e.g., `from models import DataGateway`) - configured via `pythonpath = ["src"]` in pyproject.toml
- Technical indicators use lowercase column names (`close`, `open`, `high`, `low`)
- Timestamps stored as naive UTC in SQLite
- Tests use pytest with `@pytest.mark.integration` for API tests
- Signal dictionaries: `{'action': 'BUY'|'SELL'|'HOLD', 'symbol': str, 'price': float, ...}`
