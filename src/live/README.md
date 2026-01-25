# Live Module

Real-time trading engine for paper and live trading.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `live_engine.py` | `LiveTradingEngine` | Main live trading orchestrator |
| | `LivePosition` | Track position with unrealized/realized P&L |
| | `EngineMetrics` | Runtime statistics |

## Usage

```python
from live import LiveTradingEngine
from gateway import AlpacaDataGateway, AlpacaTradingGateway
from strategy import MACDStrategy
from config import TradingConfig, RiskConfig, StopLossConfig

# Configure
config = TradingConfig(paper_mode=True, dry_run=False)
risk = RiskConfig(max_position_size=1000)
stops = StopLossConfig(position_stop_pct=0.02, trailing_stop_pct=0.05)

# Create engine
engine = LiveTradingEngine(
    config=config,
    risk_config=risk,
    stop_config=stops,
    strategy=MACDStrategy(),
    position_sizer=PercentSizer(0.10),
    data_gateway=AlpacaDataGateway(),
    trading_gateway=AlpacaTradingGateway(),
)

# Run
engine.run(
    symbols=["AAPL", "MSFT"],
    data_type=DataType.TRADES,
)
```

## Trading Modes

| Mode | Data Source | Order Execution |
|------|-------------|-----------------|
| `dry_run=True` | Historical replay | Simulated fills |
| `paper_mode=True` | Real-time WebSocket | Alpaca paper account |
| `paper_mode=False` | Real-time WebSocket | **REAL MONEY** |

## LivePosition

Tracks per-symbol position state:

```python
@dataclass
class LivePosition:
    symbol: str
    quantity: float
    average_cost: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def update_price(self, current_price: float):
        self.unrealized_pnl = (current_price - self.average_cost) * self.quantity
```

## Event Flow

```
WebSocket Tick → _on_market_data()
    → RiskManager.check_stops()     # Exit if stop triggered
    → Strategy.generate_signals()   # Generate new signals
    → OrderValidator.validate()     # Check rate/position limits
    → PositionSizer.calculate_qty()
    → _execute_order()              # Submit to TradingGateway
    → _process_fill()               # Update LivePosition
    → OrderGateway.log_*()          # Audit trail
```

## Safety Features

- Circuit breaker on portfolio-level drawdown
- Per-position stop-loss (fixed and trailing)
- Rate limiting on order submission
- Dry-run mode for testing without API calls
