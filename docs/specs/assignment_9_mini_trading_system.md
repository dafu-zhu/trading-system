# Assignment 9: Mini Trading System

**Due: Tue Nov 18, 2025 11:59pm**

**Attempt 1**  
Submitted on Nov 18, 2025 7:17pm  
**NEXT UP: Review Feedback**

**Unlimited Attempts Allowed**

---

## 🧩 Project: Mini Trading System

### 📘 Overview

In this project, you will progressively build the core components of a simple trading system. Each part focuses on a key subsystem used in electronic trading:

| Part | Focus | Concepts Practiced |
|------|-------|-------------------|
| 1 | FIX Message Parser | String parsing, dictionaries |
| 2 | Order Lifecycle Simulator | State machines, enums |
| 3 | Risk Check Engine | Validation logic, exceptions |
| 4 | Event Logger | Structured logging, replay |

You will finish by connecting all parts into one small end-to-end flow:

```
FIX → Parser → Order → RiskEngine → Logger
```

---

## 🧩 Part 1 – FIX Message Parser

### Goal

Convert raw FIX protocol strings into structured Python dictionaries.

1. Implement the parser.
2. Add validation for required tags like for price and side.
3. Raise a `ValueError` if any are missing.
4. Test using both order and quote messages.

You can use the following links to learn more about the FIX schema. You do not need to write checks for every field, but you should at least implement and check for the fields we will need to implement the risk engine below.

You may use sample FIX messages from the web, or create your own FIX message generator.

- https://fixparser.targetcompid.com/
- https://ref.onixs.biz/fix-message.html

```python
# fix_parser.py
class FixParser:
    pass

if __name__ == "__main__":
    msg = "8=FIX.4.2|35=D|55=AAPL|54=1|38=100|40=2|10=128"
    print(FixParser().parse(msg))
```

---

## 🧩 Part 2 – Order Lifecycle Simulator

### Goal

Represent an order's journey from creation to completion.

1. Implement an `Order` class to hold order details.
2. Implement a `transition()` method that will transition an order from one state to another and log when a transition state is not allowed.

```python
# order.py
from enum import Enum, auto

class OrderState(Enum):
    NEW = auto()
    ACKED = auto()
    FILLED = auto()
    CANCELED = auto()
    REJECTED = auto()

class Order:
    def __init__(self, symbol, qty, side):
        self.state = OrderState.NEW
    
    def transition(self, new_state):
        allowed = {
            OrderState.NEW: {OrderState.ACKED, OrderState.REJECTED},
            OrderState.ACKED: {OrderState.FILLED, OrderState.CANCELED},
        }
```

---

## 🧩 Part 3 – Risk Check Engine

### Goal

Block trades that exceed position or order-size limits.

1. `check()` method should validate an order against max_position and order size.
2. `RiskEngine` should be able to check orders against many equities, not just one.
3. Call `check()` before acknowledging an order.
4. Update position after a fill.
5. Print or log any rejections.

```python
# risk_engine.py
class RiskEngine:
    def __init__(self, max_order_size=1000, max_position=2000):
        pass
    
    def check(self, order) -> bool:
        pass
    
    def update_position(self, order):
        pass
```

---

## 🧩 Part 4 – Event Logger

### Goal

Record system activity for replay and analysis.

1. Create a singleton logger class.
2. Log every order creation, state change, and risk event.
3. Save to `events.json`.

```python
# logger.py
from datetime import import datetime
import json

class Logger:
    def __init__(self, path="events.json"):
    
    def log(self, event_type, data):
        pass
    
    def save(self):
        pass
```

---

## ⚙️ Integration – `main.py`

Bring everything together.

The following example shows handling of a single message. Your main should handle many messages.

```python
from fix_parser import FixParser
from order import Order, OrderState
from risk_engine import RiskEngine
from logger import Logger

fix = FixParser()
risk = RiskEngine()
log = Logger()

raw = "8=FIX.4.2|35=D|55=AAPL|54=1|38=500|40=2|10=128"
msg = fix.parse(raw)

order = Order(msg["55"], int(msg["38"]), msg["54"])
log.log("OrderCreated", msg)

try:
    risk.check(order)
    order.transition(OrderState.ACKED)
    risk.update_position(order)
    order.transition(OrderState.FILLED)
    log.log("OrderFilled", {"symbol": order.symbol, "qty": order.qty})
except ValueError as e:
    order.transition(OrderState.REJECTED)
    log.log("OrderRejected", {"reason": str(e)})

log.save()
```

### Example Output

```
[LOG] OrderCreated → {'55': 'AAPL', '38': '500', '54': '1', ...}
Order AAPL is now ACKED
Order AAPL is now FILLED
[LOG] OrderFilled → {'symbol': 'AAPL', 'qty': 500}
```

---

## ✅ Submission

Submit `fix_parser.py`, `order.py`, `risk_engine.py`, `logger.py`, and `main.py`.

- Include unit tests.
- Provide a `coverage_report.md` showing results of coverage and unit tests.
- Include `events.json` in your submission.
