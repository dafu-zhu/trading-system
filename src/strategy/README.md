# Strategy Module

Trading signal generation strategies.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `macd_strategy.py` | `MACDStrategy` | MACD crossover signals |
| `momentum_strategy.py` | `MomentumStrategy` | Momentum-based signals |
| `alpha_strategy.py` | `AlphaStrategy` | Multi-factor alpha signals |
| `alpha_weights.py` | `AlphaWeights` | Factor weight configuration |

## Strategy Interface

All strategies implement `Strategy` ABC from `models.py`:

```python
from models import Strategy, MarketSnapshot

class MyStrategy(Strategy):
    def generate_signals(self, snapshot: MarketSnapshot) -> list:
        """
        Args:
            snapshot: MarketSnapshot with timestamp, prices dict, bars dict

        Returns:
            List of signal dicts: [{"action": "BUY", "symbol": "AAPL", "price": 150.0}]
        """
        signals = []
        for symbol, price in snapshot.prices.items():
            if self.should_buy(symbol, snapshot):
                signals.append({
                    "action": "BUY",
                    "symbol": symbol,
                    "price": price,
                })
        return signals
```

## MACDStrategy

```python
from strategy import MACDStrategy

strategy = MACDStrategy(
    fast_period=12,
    slow_period=26,
    signal_period=9,
)

# Signal logic:
# BUY:  MACD crosses above signal line
# SELL: MACD crosses below signal line
# HOLD: No crossover
```

## MomentumStrategy

```python
from strategy import MomentumStrategy

strategy = MomentumStrategy(
    lookback_period=20,
    threshold=0.02,  # 2% momentum threshold
)

# Signal logic:
# BUY:  price > price[lookback] * (1 + threshold)
# SELL: price < price[lookback] * (1 - threshold)
```

## AlphaStrategy

Multi-factor strategy combining multiple signals:

```python
from strategy import AlphaStrategy
from config import AlphaConfig

config = AlphaConfig(
    factors=["momentum", "mean_reversion", "volatility"],
    weights=[0.4, 0.3, 0.3],
)

strategy = AlphaStrategy(config)
```

## MarketSnapshot

Input to all strategies:

```python
@dataclass
class MarketSnapshot:
    timestamp: datetime
    prices: dict[str, float]      # symbol -> current price
    bars: Optional[dict[str, Bar]] # symbol -> current bar (with OHLCV)
```

## Signal Format

```python
{
    "action": "BUY" | "SELL" | "HOLD",
    "symbol": "AAPL",
    "price": 150.0,
    "timestamp": datetime(...),
    # Optional fields:
    "stop_loss": 147.0,
    "take_profit": 160.0,
    "confidence": 0.85,
}
```
