# Backtester Module

Core backtesting engine for running strategy simulations on historical data.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `backtest_engine.py` | `BacktestEngine` | Main orchestrator for backtesting |
| `position_sizer.py` | `PositionSizer` (ABC) | Abstract base for position sizing |
| | `PercentSizer` | Size as % of equity |
| | `FixedSizer` | Fixed quantity |
| | `RiskBasedSizer` | Size by risk/stop distance |
| | `KellySizer` | Kelly Criterion sizing |
| | `VolatilitySizer` | ATR-based sizing |
| `trade_tracker.py` | `TradeTracker` | FIFO matching of entry/exit fills |
| `equity_tracker.py` | `EquityTracker` | Track portfolio value over time |

## Usage

```python
from backtester import BacktestEngine, PercentSizer
from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.macd_strategy import MACDStrategy
from models import Timeframe, TimeInForce

gateway = AlpacaDataGateway()
gateway.connect()

engine = BacktestEngine(
    gateway=gateway,
    strategy=MACDStrategy(),
    init_capital=100000,
    position_sizer=PercentSizer(equity_percent=0.10),
    slippage_bps=5.0,
    time_in_force=TimeInForce.IOC,
)

# Single symbol
results = engine.run(
    symbol="AAPL",
    timeframe=Timeframe.DAY_1,
    start=datetime(2024, 1, 1),
    end=datetime(2024, 6, 1),
)

# Multiple symbols
results = engine.run_multi(
    symbols=["AAPL", "MSFT", "GOOGL"],
    timeframe=Timeframe.DAY_1,
    start=datetime(2024, 1, 1),
    end=datetime(2024, 6, 1),
)
```

## Time In Force Policies

| Policy | Behavior |
|--------|----------|
| `FOK` | Fill-or-Kill: all or nothing |
| `IOC` | Immediate-or-Cancel: fill what you can, cancel rest |
| `GTC` | Good-Till-Canceled: carry unfilled portion forward |

## Data Flow

```
Bar Stream → MarketSnapshot → Strategy.generate_signals()
    → PositionSizer.calculate_qty() → OrderManager.validate()
    → DeterministicMatchingEngine.match() → TradeTracker.process_fill()
    → Portfolio.update() → EquityTracker.record()
```
