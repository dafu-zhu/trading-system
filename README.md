# Trading System

[![CI](https://github.com/dafu-zhu/alpaca-trading-system/actions/workflows/ci.yml/badge.svg)](https://github.com/dafu-zhu/alpaca-trading-system/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/dafu-zhu/alpaca-trading-system/branch/main/graph/badge.svg)](https://codecov.io/gh/dafu-zhu/alpaca-trading-system)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

An event-driven algorithmic trading system supporting backtesting and live trading through multiple data providers.

## Features

| Feature | Description |
|---------|-------------|
| **Backtesting** | Historical simulation with configurable slippage, volume limits, and time-in-force policies |
| **Live Trading** | Paper and live trading via Alpaca API with real-time WebSocket streaming |
| **Multi-Provider** | Alpaca (stocks + crypto), Coinbase (crypto), Finnhub (stocks) |
| **Risk Management** | Position stops, trailing stops, portfolio circuit breaker |
| **Strategies** | MACD crossover, momentum, multi-factor alpha |

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/dafu-zhu/alpaca-trading-system.git
cd alpaca-trading-system

# Install dependencies (requires uv)
uv sync
```

### Configuration

```bash
# Copy environment template
cp deploy/trading-system.env.example .env

# Edit with your API credentials
# Required: ALPACA_API_KEY, ALPACA_API_SECRET
```

### Run Backtest

```bash
# Basic backtest
python run_backtest.py --symbol AAPL --start 2024-01-01 --end 2024-06-01

# With custom parameters
python run_backtest.py --symbol MSFT --timeframe 1Hour --capital 50000 --position-size 0.05
```

### Run Live Trading

```bash
# Dry run (historical replay, no API)
python run_live.py --symbols AAPL,MSFT --dry-run --replay-days 5

# Paper trading (real-time data, simulated orders)
python run_live.py --symbols AAPL,MSFT --paper

# With config file
python run_live.py --symbols AAPL --config config/live_trading.yaml --paper
```

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Entry     │     │    Data      │     │   Strategy   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ run_backtest │────▶│ DataGateway  │────▶│ MACD/Alpha   │
│ run_live     │     │ BarStorage   │     │ Signals      │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
        ┌────────────────────────────────────────┘
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Sizing     │     │    Order     │     │   Matching   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ PercentSizer │────▶│ OrderManager │────▶│ Deterministic│
│ KellySizer   │     │ Validator    │     │ AlpacaAPI    │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
        ┌────────────────────────────────────────┘
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Risk      │     │  Portfolio   │     │  Analytics   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ RiskManager  │◀───▶│ Positions    │────▶│ EquityTracker│
│ StopLoss     │     │ Cash         │     │ TradeTracker │
└──────────────┘     └──────────────┘     └──────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed documentation.

## Project Structure

```
src/
├── models.py              # Core abstractions (Bar, Order, Strategy interfaces)
├── portfolio.py           # Position management (composite pattern)
├── gateway/               # Data and trading connectivity
├── strategy/              # Signal generation (MACD, momentum, alpha)
├── backtester/            # Simulation engine, position sizing, tracking
├── orders/                # Order lifecycle, validation, matching
├── risk/                  # Stop-loss, circuit breaker
├── live/                  # Real-time trading engine
├── config/                # Configuration dataclasses
├── data_loader/           # SQLite caching, technical indicators
├── analytics/             # Performance metrics
└── logger/                # Logging setup
```

## Data Providers

| Provider | Asset Types | Real-time | Cost |
|----------|-------------|-----------|------|
| **Alpaca** | Stocks, Crypto | Yes (premium for stocks) | Free tier available |
| **Coinbase** | Crypto | Yes | Free, no auth |
| **Finnhub** | Stocks | Yes | Free tier (60 req/min) |

## Development

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

### Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run pyright src/
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPACA_API_KEY` | Yes* | Alpaca API key |
| `ALPACA_API_SECRET` | Yes* | Alpaca API secret |
| `FINNHUB_API_KEY` | No | Finnhub API key (for stock streaming) |
| `TRADING_DRY_RUN` | No | Enable dry-run mode (default: false) |
| `TRADING_PAPER_MODE` | No | Use paper trading (default: true) |

*Not required if `TRADING_DRY_RUN=true`

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and module reference |
| [DEPLOYMENT.md](deploy/DEPLOYMENT.md) | Production deployment guide |
| [CLAUDE.md](CLAUDE.md) | Development conventions |

Each module in `src/` contains its own `README.md` with usage examples.

## License

MIT License - see [LICENSE](LICENSE) for details.
