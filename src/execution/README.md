# Execution Module

Order execution strategies and rebalancing tools.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `rebalancing_plan.py` | `RebalancingPlanner` | Generate trades to reach target weights |
| | `RebalancingPlan` | Container for planned trades |
| | `PlannedTrade` | Single trade in a plan |
| `twap_executor.py` | `TWAPExecutor` | Time-Weighted Average Price execution |
| | `OrderSlice` | Single slice of a TWAP order |
| | `ExecutionReport` | Summary of TWAP execution |
| `rate_limited_queue.py` | `RateLimitedOrderQueue` | Rate-limited order submission |
| | `OrderResult` | Result of order submission |
| `execution_monitor.py` | `ExecutionMonitor` | Track execution progress |
| | `CompletionStatus` | Execution completion state |
| `aggressive_handler.py` | `AggressiveCompletionHandler` | Handle incomplete fills |

## Usage

### Rebalancing

```python
from execution import RebalancingPlanner, RebalancingPlan

planner = RebalancingPlanner()

# Current positions
current = {"AAPL": 100, "MSFT": 50}

# Target weights
target = {"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3}

plan = planner.create_plan(
    current_positions=current,
    target_weights=target,
    portfolio_value=100000,
    prices={"AAPL": 150, "MSFT": 300, "GOOGL": 140},
)

for trade in plan.trades:
    print(f"{trade.symbol}: {trade.side} {trade.quantity}")
```

### TWAP Execution

```python
from execution import TWAPExecutor

executor = TWAPExecutor(
    trading_gateway=gateway,
    num_slices=10,
    interval_seconds=60,
)

report = executor.execute(
    symbol="AAPL",
    total_quantity=1000,
    side=OrderSide.BUY,
)

print(f"Filled: {report.filled_quantity} @ avg ${report.avg_price:.2f}")
```

### Rate-Limited Queue

```python
from execution import RateLimitedOrderQueue

queue = RateLimitedOrderQueue(
    trading_gateway=gateway,
    max_orders_per_minute=100,
)

queue.submit(order1)
queue.submit(order2)  # Automatically rate-limited
```

## Execution Strategies

| Strategy | Use Case |
|----------|----------|
| TWAP | Large orders, minimize market impact |
| Aggressive | Need immediate fill, accept slippage |
| Rate-Limited | Stay within API limits |
