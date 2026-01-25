# Data Loader Module

Data storage and technical indicator calculation.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `storage.py` | `BarStorage` | SQLite-based OHLCV bar storage |

### features/

| File | Class | Purpose |
|------|-------|---------|
| `calculator.py` | `FeatureCalculator` | Calculate technical indicators |
| `basic.py` | Various | Basic feature calculations |
| `alpha_loader.py` | `AlphaLoader` | Load alpha factors |

## Usage

### Bar Storage

```python
from data_loader.storage import BarStorage
from models import Bar, Timeframe

storage = BarStorage("data/trading.db")

# Save bars
storage.save_bars(bars, symbol="AAPL", timeframe=Timeframe.DAY_1)

# Load bars
bars = storage.load_bars(
    symbol="AAPL",
    timeframe=Timeframe.DAY_1,
    start=datetime(2024, 1, 1),
    end=datetime(2024, 6, 1),
)

# Check data availability
has_data = storage.has_data(symbol="AAPL", timeframe=Timeframe.DAY_1)
```

### Feature Calculator

```python
from data_loader.features.calculator import FeatureCalculator, FeatureParams

calc = FeatureCalculator()

# Calculate all indicators
df = calc.calculate_all(
    df,
    params=FeatureParams(
        macd=(12, 26, 9),
        rsi_window=14,
        bb_window=20,
        atr_window=14,
    )
)

# Columns added: macd, macd_signal, macd_hist, rsi, bb_upper, bb_middle, bb_lower, atr
```

## Database Schema

```sql
CREATE TABLE bars (
    symbol TEXT,
    timestamp DATETIME,
    timeframe TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (symbol, timestamp, timeframe)
);
```

## Indicators Supported

| Indicator | Parameters | Columns |
|-----------|------------|---------|
| MACD | fast, slow, signal | `macd`, `macd_signal`, `macd_hist` |
| RSI | window | `rsi` |
| Bollinger Bands | window, std | `bb_upper`, `bb_middle`, `bb_lower` |
| ATR | window | `atr` |
| Moving Averages | windows | `ma_5`, `ma_10`, `ma_20`, `ma_50`, `ma_200` |
