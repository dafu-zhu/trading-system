# Alpha-Based Strategy and Execution Module

This document describes the alpha-based multi-symbol trading system added in the `feature/alpha-strategy` branch.

## Overview

The alpha-strategy feature enables **cross-sectional trading** - ranking multiple symbols by alpha signals and trading the top/bottom performers. This differs from the existing single-symbol MACD strategy which generates independent signals per symbol.

**Key capabilities:**
- Multi-symbol backtesting and live trading
- Alpha signal loading with TTL-based caching
- **Dynamic alpha weighting** via pluggable weight models
- Cross-sectional ranking and threshold-based signal generation
- TWAP execution with rate limiting
- Execution quality monitoring (VWAP, slippage)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                                │
├─────────────────────────────────────────────────────────────────┤
│  AlphaLoader ──────► Cache (TTL) ──────► Alpha DataFrames       │
│       │                                                          │
│       ▼                                                          │
│  Built-in Alphas: momentum_20d, mean_reversion, cross_sectional │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Strategy Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  MarketSnapshot ──► AlphaStrategy ──► Signals (BUY/SELL/HOLD)   │
│  (multi-symbol)     (cross-sectional ranking)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Execution Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  RebalancingPlanner ──► TWAPExecutor ──► RateLimitedQueue       │
│         │                    │                   │               │
│         ▼                    ▼                   ▼               │
│  PlannedTrades         OrderSlices         OrderResults         │
│                              │                                   │
│                              ▼                                   │
│                    ExecutionMonitor (VWAP/slippage)             │
│                              │                                   │
│                              ▼                                   │
│                    AggressiveHandler (EOD completion)           │
└─────────────────────────────────────────────────────────────────┘
```

## File Reference

### Core Interface Changes

#### `src/models.py`

**New: `MarketSnapshot` dataclass**

```python
@dataclass
class MarketSnapshot:
    """Point-in-time view of market state across multiple symbols."""
    timestamp: datetime.datetime
    prices: dict[str, float]      # symbol -> current price
    bars: Optional[dict[str, Bar]] = None  # symbol -> current bar
```

**Modified: `Strategy` ABC**

```python
# Before
def generate_signals(self, tick: MarketDataPoint) -> list:

# After
def generate_signals(self, snapshot: MarketSnapshot) -> list:
```

This breaking change allows strategies to see all symbols simultaneously, enabling cross-sectional analysis.

---

### Alpha Loading

#### `src/data_loader/features/alpha_loader.py`

Loads alpha signals with TTL-based caching. Supports built-in alphas and extensible for custom alphas.

**Classes:**
- `AlphaLoaderConfig` - Configuration (cache TTL, lookback days)
- `AlphaLoader` - Main loader with caching

**Built-in Alphas:**
| Alpha | Description |
|-------|-------------|
| `momentum_20d` | 20-day price momentum (returns) |
| `mean_reversion` | Z-score of price vs 20-day MA |
| `cross_sectional_momentum` | Momentum ranked across symbols |

**Usage:**
```python
from data_loader.features.alpha_loader import AlphaLoader, AlphaLoaderConfig

config = AlphaLoaderConfig(cache_ttl_minutes=60, lookback_days=252)
loader = AlphaLoader(config)

# Load alpha for date range
df = loader.load_alpha("momentum_20d", ["AAPL", "MSFT"], start, end)

# Get alpha for specific date (returns dict)
alphas = loader.get_alpha_for_date("momentum_20d", ["AAPL", "MSFT"], date)
# {'AAPL': 0.15, 'MSFT': -0.05}
```

**Integration:** Used by `AlphaStrategy` to fetch daily alpha values.

---

### Alpha Weight Models

#### `src/strategy/alpha_weights.py`

Extensible framework for computing alpha weights dynamically. Allows strategies to use different weighting schemes without code changes.

**Classes:**
| Class | Description |
|-------|-------------|
| `AlphaWeightModel` | Abstract base class for custom models |
| `EqualWeightModel` | 1/N weight to each alpha (default) |

**Usage:**
```python
from strategy.alpha_weights import EqualWeightModel

model = EqualWeightModel()
result = model.compute_weights(["momentum", "value", "quality"])
# result.weights = {"momentum": 0.333, "value": 0.333, "quality": 0.333}
```

**Integration with AlphaStrategy:**
```python
from strategy.alpha_strategy import AlphaStrategy

# Uses EqualWeightModel by default
strategy = AlphaStrategy(symbols=["AAPL", "MSFT"], config=config)

# Get current weights after signal generation
weights = strategy.get_current_weights()
print(weights.weights)  # {"momentum_20d": 0.5, "mean_reversion": 0.5}
```

**Extending with Custom Models:**
```python
from strategy.alpha_weights import AlphaWeightModel, WeightResult

class MyCustomWeightModel(AlphaWeightModel):
    @property
    def name(self) -> str:
        return "custom"

    def compute_weights(self, alpha_names, **kwargs) -> WeightResult:
        # Your custom weighting logic
        weights = {name: 1.0 / len(alpha_names) for name in alpha_names}
        return WeightResult(weights=weights, metadata={"model": self.name})
```

---

### Alpha Strategy

#### `src/strategy/alpha_strategy.py`

Cross-sectional strategy that ranks symbols by combined alpha and generates signals based on thresholds.

**Classes:**
- `AlphaStrategyConfig` - Strategy parameters
- `AlphaStrategy` - Implements `Strategy` ABC

**Signal Logic:**
1. Compute weights using `weight_model` (or config weights if no model)
2. Load alphas for each symbol
3. Combine alphas using computed weights
4. Rank symbols by combined alpha
5. BUY top `max_positions` symbols above `long_threshold`
6. SELL bottom `max_positions` symbols below `short_threshold`
7. HOLD everything else

**Usage:**
```python
from strategy.alpha_strategy import AlphaStrategy, AlphaStrategyConfig
from data_loader.features.alpha_loader import AlphaLoader

config = AlphaStrategyConfig(
    alpha_names=["momentum_20d", "mean_reversion"],
    alpha_weights={"momentum_20d": 0.6, "mean_reversion": 0.4},
    long_threshold=0.3,
    short_threshold=-0.3,
    max_positions=5,
)

strategy = AlphaStrategy(
    symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    config=config,
    alpha_loader=AlphaLoader(),
)

# Generate signals from snapshot
signals = strategy.generate_signals(snapshot)
```

**Integration:** Drop-in replacement for `MACDStrategy` in `BacktestEngine` or `LiveEngine`.

---

### Alpha Configuration

#### `src/config/alpha_config.py`

YAML configuration loading with validation.

**Functions:**
- `load_alpha_config(path)` - Load from YAML file
- `parse_alpha_config(dict)` - Parse from dictionary
- `save_alpha_config(config, path)` - Save to YAML

**YAML Format:**
```yaml
strategy:
  type: alpha
  alphas:
    - momentum_20d
    - mean_reversion
  weights:
    momentum_20d: 0.6
    mean_reversion: 0.4
  thresholds:
    long: 0.5
    short: -0.5
  refresh: daily
  max_positions: 10
```

**Validation:**
- At least one alpha required
- Weights must sum to 1.0
- `long_threshold` must be > `short_threshold`
- Refresh frequency must be `daily` or `intraday`

---

### Execution Module

#### `src/execution/rebalancing_plan.py`

Computes required trades to move from current positions to target positions.

**Classes:**
- `PlannedTrade` - Single trade with symbol, side, quantity, priority
- `RebalancingPlan` - Collection of planned trades with metadata
- `RebalancingPlanner` - Creates plans from position diffs

**Usage:**
```python
from execution.rebalancing_plan import RebalancingPlanner

planner = RebalancingPlanner(
    start_time=time(9, 30),
    aggressive_time=time(15, 30),
)

current = {"AAPL": 100, "MSFT": 50}
target = {"AAPL": 150, "MSFT": 0, "GOOGL": 75}

plan = planner.create_plan(current, target)
# plan.trades = [
#   PlannedTrade("AAPL", BUY, 50),
#   PlannedTrade("MSFT", SELL, 50),
#   PlannedTrade("GOOGL", BUY, 75),
# ]
```

**Integration:** Used by execution layer to determine what orders to place.

---

#### `src/execution/twap_executor.py`

TWAP (Time-Weighted Average Price) execution algorithm. Splits orders into equal slices distributed across the trading window.

**Classes:**
- `OrderSlice` - Single time slice of an order
- `ExecutionReport` - Summary of execution results
- `TWAPExecutor` - Main executor

**Usage:**
```python
from execution.twap_executor import TWAPExecutor

executor = TWAPExecutor(
    trading_gateway=alpaca_gateway,
    rate_limit=200,      # Alpaca limit
    num_slices=10,       # Split each order into 10 slices
    dry_run=False,
)

report = executor.execute_plan(plan)
print(f"Completed: {report.completed_trades}/{report.total_trades}")
```

**Integration:** Uses `TradingGateway` from `models.py` to submit orders.

---

#### `src/execution/rate_limited_queue.py`

Priority queue with rate limiting for order submission.

**Classes:**
- `QueuedOrder` - Order with priority
- `OrderResult` - Result of order execution
- `RateLimitedOrderQueue` - Main queue

**Features:**
- Priority-based processing (higher priority first)
- Rate limiting (default 200/minute for Alpaca)
- Capacity tracking

**Usage:**
```python
from execution.rate_limited_queue import RateLimitedOrderQueue, QueuedOrder

queue = RateLimitedOrderQueue(max_per_minute=200)

queue.enqueue(QueuedOrder("AAPL", OrderSide.BUY, 100, priority=10))
queue.enqueue(QueuedOrder("MSFT", OrderSide.BUY, 50, priority=5))

results = queue.process_batch()  # Processes up to 200 orders
```

**Integration:** Used internally by `TWAPExecutor`.

---

#### `src/execution/execution_monitor.py`

Tracks execution quality metrics including VWAP comparison and slippage.

**Classes:**
- `FillRecord` - Record of a single fill
- `CompletionStatus` - Current completion status
- `ExecutionMonitor` - Main monitor

**Metrics:**
- Execution VWAP per symbol
- VWAP comparison (execution vs market) in basis points
- Slippage per symbol in basis points
- Completion percentage

**Usage:**
```python
from execution.execution_monitor import ExecutionMonitor

monitor = ExecutionMonitor()
monitor.set_planned_trades([
    {"symbol": "AAPL", "quantity": 100, "side": "buy"},
])
monitor.set_market_vwap("AAPL", 180.00)

monitor.track_fill("AAPL", "buy", 100, 181.00, datetime.now())

print(monitor.get_vwap_comparison("AAPL"))  # ~55 bps worse
print(monitor.get_completion_status().completion_pct)  # 100%
```

---

#### `src/execution/aggressive_handler.py`

Converts remaining limit orders to market orders at end of day to ensure completion.

**Classes:**
- `AggressiveOrder` - Market order converted from pending trade
- `AggressiveCompletionHandler` - Main handler

**Usage:**
```python
from execution.aggressive_handler import AggressiveCompletionHandler

handler = AggressiveCompletionHandler(cutoff_time=time(15, 30))

pending = [PlannedTrade("AAPL", OrderSide.BUY, 100, limit_price=180.0)]

# Before cutoff - returns empty
orders = handler.check_and_escalate(pending, datetime(2024, 1, 15, 14, 0))

# At/after cutoff - converts to market orders
orders = handler.check_and_escalate(pending, datetime(2024, 1, 15, 15, 30))
# [AggressiveOrder("AAPL", BUY, 100, reason="cutoff_time_reached")]
```

**Integration:** Called by execution layer to ensure all trades complete before market close.

---

### Engine Updates

#### `src/backtester/backtest_engine.py`

**New: `run_multi()` method**

```python
def run_multi(
    self,
    symbols: list[str],
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> dict:
    """Run backtest for multiple symbols simultaneously."""
```

This method:
1. Fetches bars for all symbols
2. Merges bars by timestamp
3. Creates `MarketSnapshot` for each timestamp
4. Passes snapshot to strategy
5. Processes signals for all symbols

**Usage:**
```python
engine = BacktestEngine(
    data_gateway=alpaca_gateway,
    strategy=alpha_strategy,
    initial_capital=100000,
)

results = engine.run_multi(
    symbols=["AAPL", "MSFT", "GOOGL"],
    timeframe=Timeframe.DAY_1,
    start=datetime(2023, 1, 1),
    end=datetime(2024, 1, 1),
)
```

---

#### `src/live/live_engine.py`

**Modified: Builds `MarketSnapshot` from price updates**

```python
# In _process_tick()
snapshot = MarketSnapshot(
    timestamp=tick.timestamp,
    prices=dict(self.current_prices),
    bars=None,
)
signals = self.strategy.generate_signals(snapshot)
```

The engine now maintains `current_prices` dict updated on each tick, allowing strategies to see all symbol prices.

---

### Strategy Updates

#### `src/strategy/macd_strategy.py` and `src/strategy/momentum_strategy.py`

Both updated to accept `MarketSnapshot` instead of single tick:

```python
def generate_signals(self, snapshot: MarketSnapshot) -> list:
    """Generate signals from market snapshot."""
    signals = []
    for symbol, price in snapshot.prices.items():
        tick = MarketDataPoint(
            symbol=symbol,
            timestamp=snapshot.timestamp,
            price=price,
            # ...
        )
        signal = self._generate_signal_for_tick(tick)
        if signal:
            signals.append(signal)
    return signals
```

These strategies still operate per-symbol but now iterate over all symbols in the snapshot.

---

## Integration Examples

### Example 1: Alpha Backtest

```python
from backtester.backtest_engine import BacktestEngine
from gateway.alpaca_data_gateway import AlpacaDataGateway
from strategy.alpha_strategy import AlphaStrategy, AlphaStrategyConfig
from data_loader.features.alpha_loader import AlphaLoader
from models import Timeframe

# Setup
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
config = AlphaStrategyConfig(
    alpha_names=["momentum_20d"],
    alpha_weights={"momentum_20d": 1.0},
    long_threshold=0.3,
    short_threshold=-0.3,
    max_positions=2,
)
strategy = AlphaStrategy(symbols, config, AlphaLoader())

engine = BacktestEngine(
    data_gateway=AlpacaDataGateway(),
    strategy=strategy,
    initial_capital=100000,
)

# Run multi-symbol backtest
results = engine.run_multi(
    symbols=symbols,
    timeframe=Timeframe.DAY_1,
    start=datetime(2023, 1, 1),
    end=datetime(2024, 1, 1),
)
```

### Example 2: Rebalancing Execution

```python
from execution.rebalancing_plan import RebalancingPlanner
from execution.twap_executor import TWAPExecutor
from execution.execution_monitor import ExecutionMonitor
from gateway.alpaca_trading_gateway import AlpacaTradingGateway

# Current and target positions from strategy
current = {"AAPL": 100, "MSFT": 50, "GOOGL": 0}
target = {"AAPL": 50, "MSFT": 100, "GOOGL": 75}

# Create rebalancing plan
planner = RebalancingPlanner()
plan = planner.create_plan(current, target)

# Execute with TWAP
gateway = AlpacaTradingGateway()
executor = TWAPExecutor(trading_gateway=gateway, num_slices=10)
report = executor.execute_plan(plan)

# Monitor quality
monitor = ExecutionMonitor()
# ... track fills and check slippage
```

### Example 3: Load Config from YAML

```python
from config.alpha_config import load_alpha_config
from strategy.alpha_strategy import AlphaStrategy
from data_loader.features.alpha_loader import AlphaLoader

config = load_alpha_config("config/alpha_strategy.yaml")
strategy = AlphaStrategy(
    symbols=["AAPL", "MSFT", "GOOGL"],
    config=config,
    alpha_loader=AlphaLoader(),
)
```

---

## Testing

```bash
# Run all alpha-related tests
uv run pytest tests/test_alpha_strategy.py tests/test_rebalancing_execution.py -v

# Run specific test class
uv run pytest tests/test_alpha_strategy.py::TestAlphaLoader -v

# Run with coverage
uv run pytest tests/test_alpha_strategy.py --cov=src/strategy --cov=src/data_loader
```

**Test coverage:**
- `TestAlphaLoader` - 7 tests for alpha loading and caching
- `TestAlphaStrategy` - 9 tests for signal generation
- `TestAlphaConfig` - 7 tests for configuration validation
- `TestRebalancingPlan` - 5 tests for plan creation
- `TestTWAPExecutor` - 5 tests for TWAP execution
- `TestRateLimitedQueue` - 4 tests for rate limiting
- `TestExecutionMonitor` - 5 tests for quality tracking
- `TestAggressiveHandler` - 5 tests for EOD handling

---

## Future Work

1. **quantdl Integration** - Replace mock alpha calculations with real quantdl data
2. **Alpha Combiner** - More sophisticated alpha combination (IC weighting, etc.)
3. **Portfolio Optimizer** - Mean-variance optimization for target positions
4. **Real-time Alpha Updates** - Intraday alpha refresh for HF strategies
5. **Execution Analytics** - Historical execution quality dashboard
