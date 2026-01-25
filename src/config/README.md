# Config Module

Configuration dataclasses for trading system parameters.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `trading_config.py` | `TradingConfig` | API credentials, paper/live mode |
| | `RiskConfig` | Position limits, rate limits |
| | `StopLossConfig` | Stop-loss parameters |
| | `LiveEngineConfig` | Live engine settings |
| | `DataType` | Enum: TRADES, QUOTES, BARS |
| | `AssetType` | Enum: STOCK, CRYPTO |
| `alpha_config.py` | `AlphaConfig` | Alpha strategy configuration |

## Usage

```python
from config import TradingConfig, RiskConfig, StopLossConfig

# Load from environment
trading = TradingConfig(
    api_key=os.getenv("ALPACA_API_KEY"),
    api_secret=os.getenv("ALPACA_API_SECRET"),
    paper_mode=True,
    dry_run=False,
)

# Risk parameters
risk = RiskConfig(
    max_position_size=1000,
    max_position_value=100000,
    max_orders_per_minute=200,
)

# Stop-loss settings
stops = StopLossConfig(
    position_stop_pct=0.02,      # 2% fixed stop
    trailing_stop_pct=0.05,      # 5% trailing stop
    portfolio_stop_pct=0.10,     # 10% daily loss limit
)
```

## Environment Variables

```bash
ALPACA_API_KEY=<your-key>
ALPACA_API_SECRET=<your-secret>
ALPACA_BASE_URL=https://paper-api.alpaca.markets
TRADING_DRY_RUN=true
TRADING_PAPER_MODE=true
```
