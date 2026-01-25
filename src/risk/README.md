# Risk Module

Risk management and stop-loss handling.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `risk_manager.py` | `RiskManager` | Stop-loss and circuit breaker management |
| | `PositionStop` | Per-position stop tracking |
| | `ExitSignal` | Generated when stop triggered |
| | `StopType` | Enum: FIXED_PERCENT, TRAILING_PERCENT, ABSOLUTE_PRICE |
| `risk_engine.py` | `RiskEngine` | Order-level risk checks |

## Usage

### RiskManager

```python
from risk import RiskManager
from config import StopLossConfig

config = StopLossConfig(
    position_stop_pct=0.02,      # 2% fixed stop
    trailing_stop_pct=0.05,      # 5% trailing stop
    portfolio_stop_pct=0.10,     # 10% daily loss limit
    max_drawdown_pct=0.20,       # 20% max drawdown
)

manager = RiskManager(config)

# Add position with stops
manager.add_position(
    symbol="AAPL",
    entry_price=150.0,
    quantity=100,
)

# Check stops on each tick
exit_signals = manager.check_stops(
    current_prices={"AAPL": 145.0},
    portfolio_value=95000,
    positions=[{"symbol": "AAPL", "quantity": 100}],
)

for signal in exit_signals:
    print(f"Exit {signal.symbol}: {signal.reason}")
    # Execute exit order...

# Remove when position closed
manager.remove_position("AAPL")
```

### RiskEngine

```python
from risk import RiskEngine

engine = RiskEngine(
    portfolio=portfolio,
    max_order_size=1000,
    max_position=2000,
)

is_allowed = engine.check(order)
# Checks: order size, resulting position size
```

## Stop Types

| Type | Behavior |
|------|----------|
| `FIXED_PERCENT` | Stop at fixed % below entry |
| `TRAILING_PERCENT` | Stop trails highest price |
| `ABSOLUTE_PRICE` | Stop at specific price level |

## ExitSignal

```python
@dataclass
class ExitSignal:
    symbol: str
    side: OrderSide       # Always SELL for long exits
    quantity: float       # Full position quantity
    reason: str           # "position_stop", "trailing_stop", "circuit_breaker"
    trigger_price: float  # Price that triggered the stop
```

## Circuit Breaker

Portfolio-level protection:

- **Daily loss limit**: Stop trading if daily loss exceeds threshold
- **Max drawdown**: Stop trading if portfolio drops too far from peak

```python
# Triggered when portfolio_value / high_water_mark < (1 - max_drawdown_pct)
```
