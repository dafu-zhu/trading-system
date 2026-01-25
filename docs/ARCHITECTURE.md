# Trading System Architecture

*Confluence-Ready Documentation | Last Updated: January 2026*

---

## Overview

This is an event-driven algorithmic trading system supporting backtesting and live trading through Alpaca API integration. The system processes market data through a pipeline of strategy generation, risk management, and order execution.

| Attribute | Value |
|-----------|-------|
| **Language** | Python 3.13+ |
| **Package Manager** | uv |
| **Data Provider** | Alpaca API (stocks + crypto) |
| **Storage** | SQLite (bar caching) |
| **Trading Modes** | Backtest, Dry-run, Paper, Live |

---

## System Architecture Diagram

```
+------------------+     +------------------+     +------------------+
|     ENTRY        |     |      DATA        |     |    STRATEGY      |
+------------------+     +------------------+     +------------------+
| run_backtest.py  |     | AlpacaDataGateway|     | FeatureCalculator|
| run_live.py      |---->| BarStorage       |---->| MACDStrategy     |
|                  |     | SQLite Cache     |     | MomentumStrategy |
+------------------+     +------------------+     +------------------+
                                                          |
                                 +------------------------+
                                 v
+------------------+     +------------------+     +------------------+
|     SIZING       |     |     ORDER        |     |    MATCHING      |
+------------------+     +------------------+     +------------------+
| PercentSizer     |     | Order            |     | Deterministic-   |
| FixedSizer       |<----|   NEW->FILLED    |---->| MatchingEngine   |
| KellySizer       |     | OrderManager     |     | AlpacaTrading-   |
| VolatilitySizer  |     | OrderValidator   |     |   Gateway        |
+------------------+     +------------------+     +------------------+
                                 |
                                 v
+------------------+     +------------------+     +------------------+
|      RISK        |     |   PORTFOLIO      |     |   ANALYTICS      |
+------------------+     +------------------+     +------------------+
| RiskManager      |     | Portfolio        |     | EquityTracker    |
| StopLoss         |<----|   Position tree  |---->| TradeTracker     |
| CircuitBreaker   |     |   cash tracking  |     | Performance      |
+------------------+     +------------------+     +------------------+
```

---

## Module Reference

### Data Layer

| Module | Location | Purpose | Key Classes |
|--------|----------|---------|-------------|
| **Gateway** | `src/gateway/` | External data connections | `AlpacaDataGateway`, `CoinbaseDataGateway`, `FinnhubDataGateway` |
| **Storage** | `src/data_loader/storage.py` | SQLite bar caching | `BarStorage` |
| **Features** | `src/data_loader/features/` | Technical indicators | `FeatureCalculator`, `FeatureParams` |

The **AlpacaDataGateway** implements the `DataGateway` abstract interface, providing historical bar fetching, real-time WebSocket streaming, and market calendar access. It automatically caches fetched bars in SQLite to minimize API calls.

```python
# Data flow: Alpaca API -> BarStorage (SQLite) -> Strategy
gateway = AlpacaDataGateway(use_cache=True)
gateway.connect()
bars = gateway.fetch_bars("AAPL", Timeframe.DAY_1, start, end)  # Cached
```

The **FeatureCalculator** transforms raw bar data into enriched DataFrames with technical indicators: MACD, RSI, Bollinger Bands, ATR, and moving averages (SMA/EMA).

---

### Strategy Layer

| Module | Location | Purpose | Key Classes |
|--------|----------|---------|-------------|
| **Strategy** | `src/strategy/` | Signal generation | `MACDStrategy`, `MomentumStrategy`, `AlphaStrategy` |

All strategies implement the `Strategy` abstract base class with a single method:

```python
def generate_signals(self, snapshot: MarketSnapshot) -> list[dict]
```

The **MarketSnapshot** provides a point-in-time view across multiple symbols:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | Snapshot time |
| `prices` | `dict[str, float]` | Symbol to current price mapping |
| `bars` | `dict[str, Bar]` | Optional full bar data |

Strategies return signal dictionaries with the following structure:

| Key | Value | Description |
|-----|-------|-------------|
| `action` | `BUY` / `SELL` / `HOLD` | Trading action |
| `symbol` | string | Asset symbol |
| `price` | float | Signal price |
| `timestamp` | datetime | Signal time |

---

### Position Sizing

| Sizer | Strategy | Formula |
|-------|----------|---------|
| **FixedSizer** | Fixed quantity | `qty = fixed_qty` |
| **PercentSizer** | Equity percentage | `qty = (equity * pct) / price` |
| **RiskBasedSizer** | Risk per trade | `qty = (equity * risk_pct) / stop_distance` |
| **KellySizer** | Kelly criterion | `f* = (p*b - q) / b` where p=win_rate, b=win/loss ratio |
| **VolatilitySizer** | ATR-based | `qty = (equity * risk_pct) / (ATR * multiplier)` |

All sizers implement `PositionSizer.calculate_qty(signal, portfolio, price) -> float`.

---

### Order Management

| Module | Location | Purpose | Key Classes |
|--------|----------|---------|-------------|
| **Order** | `src/orders/order.py` | Order lifecycle | `Order`, `OrderState` |
| **Manager** | `src/orders/order_manager.py` | Validation | `OrderManager` |
| **Validator** | `src/orders/order_validator.py` | Risk checks | `OrderValidator`, `ValidationResult` |
| **Matching** | `src/orders/matching_engine.py` | Fill simulation | `DeterministicMatchingEngine` |

**Order State Machine:**

```
NEW -----> ACKED -----> PARTIALLY_FILLED -----> FILLED
  |          |                |
  v          v                v
REJECTED  CANCELED         CANCELED
```

The **DeterministicMatchingEngine** provides reproducible backtest fills:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fill_at` | `"close"` | Fill price source: `open`, `close`, or `vwap` |
| `max_volume_pct` | `0.1` | Max fill as % of bar volume (10%) |
| `slippage_bps` | `0.0` | Slippage in basis points |

**Time-in-Force Policies:**

| Policy | Behavior |
|--------|----------|
| **FOK** (Fill-or-Kill) | Complete fill or cancel entire order |
| **IOC** (Immediate-or-Cancel) | Fill available, cancel remainder |
| **GTC** (Good-til-Canceled) | Carry unfilled portion to next bar |

---

### Risk Management

| Module | Location | Purpose | Key Classes |
|--------|----------|---------|-------------|
| **Risk** | `src/risk/risk_manager.py` | Stop-loss, circuit breaker | `RiskManager`, `PositionStop`, `ExitSignal` |

**RiskManager** implements multiple protection layers:

| Protection | Config Parameter | Description |
|------------|------------------|-------------|
| Position Stop | `position_stop_pct` | Fixed % from entry price |
| Trailing Stop | `trailing_stop_pct` | % from high water mark |
| Portfolio Stop | `portfolio_stop_pct` | Max daily loss % |
| Max Drawdown | `max_drawdown_pct` | Max peak-to-trough % |
| Circuit Breaker | `enable_circuit_breaker` | Halt all trading on breach |

The **OrderValidator** performs pre-trade risk checks:

| Check | Failure Code | Description |
|-------|--------------|-------------|
| Rate Limit (Global) | `RATE_LIMIT_GLOBAL` | Max orders/minute exceeded |
| Rate Limit (Symbol) | `RATE_LIMIT_SYMBOL` | Max orders/symbol/minute exceeded |
| Capital | `INSUFFICIENT_CAPITAL` | Order value > available cash |
| Position Size | `POSITION_SIZE_LIMIT` | Position exceeds max shares |
| Position Value | `POSITION_VALUE_LIMIT` | Position exceeds max dollars |
| Total Exposure | `TOTAL_EXPOSURE_LIMIT` | Portfolio exposure exceeded |

---

### Portfolio & Tracking

| Module | Location | Purpose | Key Classes |
|--------|----------|---------|-------------|
| **Portfolio** | `src/portfolio.py` | Position tree | `Portfolio`, `Position`, `PortfolioGroup` |
| **Trade Tracker** | `src/backtester/trade_tracker.py` | PnL calculation | `TradeTracker` |
| **Equity Tracker** | `src/backtester/equity_tracker.py` | Equity curve | `EquityTracker` |

The **Portfolio** uses a composite pattern (tree structure) for position management:

```
root (PortfolioGroup)
  |-- cash (Position: qty=capital, price=1)
  |-- AAPL (Position: qty=100, price=175.50)
  |-- MSFT (Position: qty=50, price=420.00)
```

The **TradeTracker** uses FIFO matching to create round-trip trades:

| Field | Type | Description |
|-------|------|-------------|
| `entry_time` | datetime | Position opened |
| `exit_time` | datetime | Position closed |
| `entry_price` | float | Entry fill price |
| `exit_price` | float | Exit fill price |
| `quantity` | float | Trade size |
| `pnl` | float | Realized P&L in dollars |
| `return` | float | Return as decimal |
| `holding_period` | float | Days held |

---

### Configuration

| Config Class | Purpose | Key Parameters |
|--------------|---------|----------------|
| `TradingConfig` | API credentials | `api_key`, `api_secret`, `paper_mode`, `dry_run` |
| `RiskConfig` | Order limits | `max_position_size`, `max_orders_per_minute` |
| `StopLossConfig` | Risk controls | `position_stop_pct`, `trailing_stop_pct` |
| `LiveEngineConfig` | Complete config | Combines all above + `enable_trading` |

Configuration can be loaded from:
- **YAML file**: `LiveEngineConfig.from_yaml("config/live_trading.yaml")`
- **Environment**: `LiveEngineConfig.from_env()` reads `ALPACA_*`, `TRADING_*`, `RISK_*`, `STOPLOSS_*` vars

---

## Engine Reference

### BacktestEngine

Processes historical bars through strategy and matching engine.

```python
engine = BacktestEngine(
    gateway=gateway,
    strategy=MACDStrategy(gateway, Timeframe.DAY_1),
    init_capital=100_000,
    position_sizer=PercentSizer(0.10),
    slippage_bps=10,
    time_in_force=TimeInForce.IOC,
)
results = engine.run(symbol="AAPL", timeframe=Timeframe.DAY_1, start=start, end=end)
```

**Execution Flow:**

| Step | Action |
|------|--------|
| 1 | Stream bars from gateway |
| 2 | Update `DeterministicMatchingEngine` with current bar |
| 3 | Try to fill pending GTC orders |
| 4 | Build `MarketSnapshot` from bar data |
| 5 | Call `strategy.generate_signals(snapshot)` |
| 6 | For BUY/SELL: calculate qty via `PositionSizer` |
| 7 | Validate via `OrderManager` |
| 8 | Match via `DeterministicMatchingEngine` |
| 9 | Process fills: update Portfolio, TradeTracker |
| 10 | Mark-to-market all positions |
| 11 | Record equity via `EquityTracker` |
| 12 | At end: close all open positions |

**Results Dictionary:**

| Key | Type | Description |
|-----|------|-------------|
| `symbol` | str | Traded symbol |
| `bar_count` | int | Bars processed |
| `initial_capital` | float | Starting capital |
| `final_value` | float | Ending portfolio value |
| `total_return_pct` | float | Return percentage |
| `total_trades` | int | Completed trades |
| `equity_curve` | list | Timestamp/value pairs |
| `trades` | list | Trade details |

---

### LiveTradingEngine

Handles real-time market data and order execution.

```python
config = LiveEngineConfig.from_yaml("config/live_trading.yaml")
engine = LiveTradingEngine(
    config=config,
    strategy=MACDStrategy(gateway, Timeframe.MIN_1),
    position_sizer=PercentSizer(0.10),
)
engine.run(symbols=["AAPL", "MSFT"])  # Blocking
```

**Operating Modes:**

| Mode | Config | Behavior |
|------|--------|----------|
| **Dry-run** | `dry_run=True` | Historical replay, simulated fills |
| **Paper** | `paper_mode=True` | Real-time data, Alpaca paper orders |
| **Live** | `paper_mode=False` | Real-time data, real orders (CAUTION) |

**Execution Flow:**

| Step | Action |
|------|--------|
| 1 | Receive `MarketDataPoint` via WebSocket |
| 2 | Update current prices, position unrealized P&L |
| 3 | Check `RiskManager.check_stops()` for stop triggers |
| 4 | If circuit breaker active: skip signal generation |
| 5 | Build `MarketSnapshot` from current prices |
| 6 | Call `strategy.generate_signals(snapshot)` |
| 7 | Skip if signal unchanged from last (deduplication) |
| 8 | Validate via `OrderValidator` |
| 9 | Execute via `TradingGateway.submit_order()` |
| 10 | Log to `OrderGateway` (CSV audit trail) |
| 11 | Write health file for monitoring |

**LivePosition Tracking:**

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | str | Asset symbol |
| `quantity` | float | Current position size |
| `average_cost` | float | Average entry price |
| `current_price` | float | Latest market price |
| `unrealized_pnl` | float | Paper gain/loss |
| `realized_pnl` | float | Locked-in gain/loss |

---

## Data Models

### Core Types (src/models.py)

| Type | Description |
|------|-------------|
| `Bar` | OHLCV bar with symbol, timestamp, timeframe |
| `MarketDataPoint` | Real-time tick with price, volume, bid/ask |
| `MarketSnapshot` | Cross-sectional view of all symbols at one time |
| `OrderSide` | `BUY` or `SELL` enum |
| `OrderType` | `MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT` |
| `TimeInForce` | `DAY`, `GTC`, `IOC`, `FOK` |
| `Timeframe` | `1Min` through `1Month` |
| `OrderResult` | Broker response with order_id, status, fills |

### Abstract Interfaces

| Interface | Methods | Implemented By |
|-----------|---------|----------------|
| `DataGateway` | `fetch_bars()`, `stream_bars()`, `stream_realtime()` | `AlpacaDataGateway` |
| `TradingGateway` | `submit_order()`, `cancel_order()`, `get_positions()` | `AlpacaTradingGateway` |
| `Strategy` | `generate_signals(snapshot)` | `MACDStrategy`, etc. |
| `MatchingEngine` | `match(order)` | `DeterministicMatchingEngine` |
| `PositionSizer` | `calculate_qty(signal, portfolio, price)` | `PercentSizer`, etc. |

---

## Quick Start Examples

### Backtest

```bash
# Single symbol
python run_backtest.py --symbol AAPL --start 2023-01-01 --end 2024-01-01

# With custom parameters
python run_backtest.py --symbol MSFT --timeframe 1Hour --capital 50000 \
    --position-size 0.05 --slippage 10 -v
```

### Live Trading

```bash
# Dry run (historical replay)
python run_live.py --symbols AAPL,MSFT --dry-run --replay-days 5

# Paper trading (real-time, simulated orders)
python run_live.py --symbols AAPL,MSFT --paper

# With config file
python run_live.py --symbols AAPL --config config/live_trading.yaml --paper
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALPACA_API_KEY` | Yes* | - | Alpaca API key |
| `ALPACA_API_SECRET` | Yes* | - | Alpaca API secret |
| `ALPACA_BASE_URL` | No | `https://paper-api.alpaca.markets` | API endpoint |
| `TRADING_DRY_RUN` | No | `false` | Simulate without API |
| `TRADING_ENABLE` | No | `true` | Enable order submission |
| `TRADING_PAPER_MODE` | No | `true` | Use paper trading |

*Not required if `TRADING_DRY_RUN=true`

---

## File Structure

```
src/
+-- models.py                 # Core abstractions (Bar, Order types, interfaces)
+-- portfolio.py              # Portfolio tree, Position class
+-- gateway/
|   +-- alpaca_data_gateway.py     # Historical + streaming data
|   +-- alpaca_trading_gateway.py  # Order submission
|   +-- order_gateway.py           # CSV audit logging
+-- strategy/
|   +-- macd_strategy.py           # MACD crossover signals
|   +-- momentum_strategy.py       # Momentum-based signals
|   +-- alpha_strategy.py          # Factor-based signals
+-- backtester/
|   +-- backtest_engine.py         # Simulation runner
|   +-- position_sizer.py          # Sizing strategies
|   +-- equity_tracker.py          # Equity curve
|   +-- trade_tracker.py           # Round-trip trade matching
+-- orders/
|   +-- order.py                   # Order state machine
|   +-- order_manager.py           # Validation wrapper
|   +-- order_validator.py         # Risk limit checks
|   +-- matching_engine.py         # Deterministic fills
+-- config/
|   +-- trading_config.py          # Configuration dataclasses
+-- risk/
|   +-- risk_manager.py            # Stop-loss, circuit breaker
+-- live/
|   +-- live_engine.py             # Real-time trading orchestration
+-- data_loader/
|   +-- storage.py                 # SQLite caching
|   +-- features/calculator.py     # Technical indicators
+-- analytics/                     # Performance metrics
+-- logger/                        # Logging setup
```

---

## Testing

```bash
# Run tests (integration tests excluded)
uv run pytest tests/

# Include integration tests (requires API credentials)
uv run pytest tests/ -m integration

# Run specific test file
uv run pytest tests/test_portfolio.py
```

---

## Related Documentation

- [CLAUDE.md](/Users/zdf/Documents/GitHub/trading-system/CLAUDE.md) - Development conventions
- [deploy/DEPLOYMENT.md](/Users/zdf/Documents/GitHub/trading-system/deploy/DEPLOYMENT.md) - Deployment guide

---

*Document generated for engineering onboarding. For questions, consult the codebase or reach out to the team.*
