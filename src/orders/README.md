# Orders Module

Order representation, validation, and matching.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `order.py` | `Order` | Order with state machine |
| | `OrderState` | Enum: NEW, ACKED, FILLED, etc. |
| | `OrderSide` | Imported from models (BUY, SELL) |
| `order_manager.py` | `OrderManager` | Pre-trade validation |
| `order_validator.py` | `OrderValidator` | Real-time risk checks |
| `matching_engine.py` | `DeterministicMatchingEngine` | Backtesting order matcher |

## Order State Machine

```
NEW → ACKED → PARTIALLY_FILLED → FILLED
         ↓           ↓
      CANCELED    CANCELED

NEW → REJECTED
```

## Usage

### Creating Orders

```python
from orders.order import Order, OrderState
from models import OrderSide

order = Order(
    symbol="AAPL",
    qty=100,
    price=150.0,
    side=OrderSide.BUY,
    timestamp=datetime.now(),
)

# State transitions
order.transition(OrderState.ACKED)

# Fill order
filled = order.fill(50)  # Partial fill
order.state  # OrderState.PARTIALLY_FILLED

filled = order.fill(50)  # Complete fill
order.state  # OrderState.FILLED

# Properties
order.is_buy        # True
order.is_filled     # True
order.is_active     # False
order.remaining_qty # 0
order.side.multiplier  # 1 (BUY=1, SELL=-1)
```

### Validation

```python
from orders.order_manager import OrderManager

manager = OrderManager(max_order_size=1000, max_position=2000)

is_valid = manager.validate_order(order, portfolio)
# Checks: capital sufficiency, risk limits
```

### Matching Engine (Backtesting)

```python
from orders.matching_engine import DeterministicMatchingEngine

engine = DeterministicMatchingEngine(
    fill_at="close",      # close, open, or vwap
    max_volume_pct=0.10,  # Max 10% of bar volume
    slippage_bps=5.0,     # 5 basis points slippage
)

engine.set_current_bar(bar)
report = engine.match(order)

# report = {
#     "status": "filled" | "partially_filled" | "rejected",
#     "filled_qty": 100,
#     "fill_price": 150.25,
#     "slippage": 0.05,
# }
```

## OrderSide

```python
from models import OrderSide

OrderSide.BUY.value       # "buy" (for API)
OrderSide.BUY.multiplier  # 1 (for calculations)

OrderSide.SELL.value      # "sell"
OrderSide.SELL.multiplier # -1
```
