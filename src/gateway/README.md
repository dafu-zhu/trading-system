# Gateway Module

Market data and trading connectivity.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `alpaca_data_gateway.py` | `AlpacaDataGateway` | Historical and real-time data from Alpaca |
| `alpaca_trading_gateway.py` | `AlpacaTradingGateway` | Order submission via Alpaca API |
| `coinbase_data_gateway.py` | `CoinbaseDataGateway` | Crypto data from Coinbase |
| `finnhub_data_gateway.py` | `FinnhubDataGateway` | Market data from Finnhub |
| `order_gateway.py` | `OrderGateway` | CSV audit logging for orders |

## Usage

### AlpacaDataGateway

```python
from gateway import AlpacaDataGateway
from models import Timeframe

gateway = AlpacaDataGateway()
gateway.connect()

# Fetch historical bars (cached to SQLite)
bars = gateway.fetch_bars(
    symbol="AAPL",
    timeframe=Timeframe.DAY_1,
    start=datetime(2024, 1, 1),
    end=datetime(2024, 6, 1),
)

# Stream bars as iterator
for bar in gateway.stream_bars("AAPL", Timeframe.DAY_1, start, end):
    process(bar)

# Real-time streaming (WebSocket)
gateway.stream_realtime(
    symbols=["AAPL", "MSFT"],
    callback=on_tick,
    data_type=DataType.TRADES,
)

# Historical replay (for dry-run)
gateway.replay_historical(
    symbols=["AAPL"],
    callback=on_tick,
    days=5,
)

gateway.disconnect()
```

### AlpacaTradingGateway

```python
from gateway import AlpacaTradingGateway
from models import OrderSide, OrderType

gateway = AlpacaTradingGateway(paper_mode=True)
gateway.connect()

# Submit order
result = gateway.submit_order(
    symbol="AAPL",
    quantity=100,
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
)

# Get positions
positions = gateway.get_positions()

# Get account info
account = gateway.get_account()

gateway.disconnect()
```

### OrderGateway (Audit Log)

```python
from gateway import OrderGateway

log = OrderGateway(log_dir="logs/orders")

log.log_order_sent(order_id=1, symbol="AAPL", side="BUY", qty=100)
log.log_order_filled(order_id=1, fill_price=150.25, filled_qty=100)
```

## Supported Timeframes

| Timeframe | Enum |
|-----------|------|
| 1 Minute | `Timeframe.MIN_1` |
| 5 Minutes | `Timeframe.MIN_5` |
| 15 Minutes | `Timeframe.MIN_15` |
| 1 Hour | `Timeframe.HOUR_1` |
| 4 Hours | `Timeframe.HOUR_4` |
| 1 Day | `Timeframe.DAY_1` |
| 1 Week | `Timeframe.WEEK_1` |
