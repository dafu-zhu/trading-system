# Understanding the `windows` Parameter Design

## Why Two Separate Fields?

```python
@dataclass
class FeatureConfig:
    name: str
    windows: Optional[list[int]] = None  # Why separate?
    params: dict = field(default_factory=dict)
```

### Design Rationale

**Separate `windows` field exists because:**

1. **Semantic difference:**
   - `windows` (plural) → generates MULTIPLE features
   - `window` (singular) → used in ONE calculation

2. **Convenience for users:**
   - One `windows=[10,20]` can apply to multiple features (MA, volatility, momentum)
   - Avoid repeating the same list

3. **Historical/practical:**
   - Common trading practice: test strategies across multiple timeframes
   - Users often want "10, 20, 50 day moving averages" together

## The Three Ways to Set Windows

### 1. General `windows` Parameter (Shortcut)

```python
# Applies to: moving_average, volatility, momentum ONLY
df = calculate(df, features=['moving_average', 'volatility'], windows=[10, 20])
```

**Flow:**
```
calculate() line 204:
  if 'windows' in kwargs and feature in [MOVING_AVERAGE, VOLATILITY, MOMENTUM]:
      specific_kwargs['windows'] = kwargs['windows']
```

### 2. Feature-Specific `windows` Parameter (Explicit)

```python
# Applies to only that feature
df = calculate(df, features=['moving_average'], moving_average_windows=[50, 200])
```

**Flow:**
```
calculate() lines 195-201:
  feature_prefix = 'moving_average_'
  specific_kwargs = {
      'windows': [50, 200]  # 'moving_average_windows' → 'windows'
  }
```

### 3. Single `window` Parameter (Different features)

```python
# For RSI, ATR, Bollinger
df = calculate(df, features=['rsi'], rsi_window=21)
```

**Flow:**
```
calculate() lines 195-201:
  feature_prefix = 'rsi_'
  specific_kwargs = {
      'window': 21  # 'rsi_window' → 'window'
  }
  # This goes into config.params, NOT config.windows!
```

## Complete Parameter Flow Diagram

```
User Input:
calculate(df,
    features=['moving_average', 'rsi'],
    windows=[10, 20],           # General (Type A only)
    rsi_window=21               # Feature-specific (Type B)
)

          ↓

feature_kwargs = {
    'windows': [10, 20],
    'rsi_window': 21
}

          ↓ ↓ ↓

=== Processing 'moving_average' ===

1. Extract feature-specific:
   feature_prefix = 'moving_average_'
   specific_kwargs = {}  # No 'moving_average_*' params

2. Check general 'windows':
   'moving_average' in [MOVING_AVERAGE, VOLATILITY, MOMENTUM]? YES
   → specific_kwargs['windows'] = [10, 20]

3. Create config:
   get_config('moving_average', windows=[10, 20])

4. Result:
   FeatureConfig(
       name='moving_average',
       windows=[10, 20],      ← Goes here
       params={}
   )

          ↓

5. Call _calc_moving_average():
   for window in config.windows:  # [10, 20]
       df[f'sma_{window}'] = ...
       df[f'ema_{window}'] = ...
   # Creates: sma_10, ema_10, sma_20, ema_20

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== Processing 'rsi' ===

1. Extract feature-specific:
   feature_prefix = 'rsi_'
   specific_kwargs = {
       'window': 21  # 'rsi_window' stripped to 'window'
   }

2. Check general 'windows':
   'rsi' in [MOVING_AVERAGE, VOLATILITY, MOMENTUM]? NO
   → Skip (general 'windows' not applied)

3. Create config:
   get_config('rsi', window=21)

   Inside get_config():
   windows = kwargs.pop('windows', None)  # None
   params = {**{'window': 14}, **{'window': 21}}

4. Result:
   FeatureConfig(
       name='rsi',
       windows=None,          ← Not used
       params={'window': 21}  ← Goes here
   )

          ↓

5. Call _calc_rsi():
   window = config.params.get('window', 14)  # 21
   delta = df[cols.close].diff()
   ...
   df['rsi'] = ...
   # Creates: rsi (single column)
```

## Feature Classification

### Type A: Multiple Variations (use `windows` plural)

| Feature | Parameter | Output Pattern | Example |
|---------|-----------|----------------|---------|
| `moving_average` | `windows=[10,20]` | `sma_{window}`, `ema_{window}` | sma_10, ema_10, sma_20, ema_20 |
| `volatility` | `windows=[10,20]` | `volatility_{window}` | volatility_10, volatility_20 |
| `momentum` | `windows=[10,20]` | `momentum_{window}`, `roc_{window}` | momentum_10, roc_10, momentum_20, roc_20 |

**Storage:** `config.windows = [10, 20]`

### Type B: Single Output (use `window` singular)

| Feature | Parameter | Output | Storage |
|---------|-----------|--------|---------|
| `rsi` | `window=14` | `rsi` | `config.params['window'] = 14` |
| `atr` | `window=14` | `atr` | `config.params['window'] = 14` |
| `bollinger` | `window=20` | `bb_upper`, `bb_lower`, etc. | `config.params['window'] = 20` |

**Storage:** `config.params['window'] = 14`

## User Input Cheat Sheet

### ✅ CORRECT Usage

```python
# Type A features - use plural 'windows'
calculate(df, features=['moving_average'], windows=[10, 20, 50])
calculate(df, features=['volatility'], volatility_windows=[5, 10])

# Type B features - use singular 'window'
calculate(df, features=['rsi'], rsi_window=21)
calculate(df, features=['bollinger'], bollinger_window=30)

# Mixed
calculate(df,
    features=['moving_average', 'rsi'],
    windows=[10, 20],      # Applies to moving_average
    rsi_window=21          # Applies to rsi
)

# Different windows for different Type A features
calculate(df,
    features=['moving_average', 'volatility'],
    moving_average_windows=[50, 200],  # MA specific
    volatility_windows=[5, 10]         # Volatility specific
)
```

### ❌ INCORRECT Usage

```python
# DON'T use 'windows' (plural) for Type B features
calculate(df, features=['rsi'], windows=[10, 20])  # ✗ No effect!

# DON'T use 'window' (singular) for Type A features
calculate(df, features=['moving_average'], moving_average_window=10)  # ✗ Wrong!

# DON'T mix up singular/plural
calculate(df, features=['rsi'], rsi_windows=[10, 20])  # ✗ Won't work!
```

## Why This Design?

### Pros:
1. **Convenience:** One `windows=[10,20]` applies to multiple related features
2. **Semantic clarity:** Plural vs singular indicates multiple vs single outputs
3. **Flexibility:** Can still override per-feature

### Cons:
1. **Inconsistency:** Special case for three features vs all others
2. **Confusion:** Users need to know which features use `windows` vs `window`
3. **Implementation complexity:** Special logic in `calculate()` at line 204

## Alternative Design (Simpler)

**Option 1: Put everything in `params`**
```python
@dataclass
class FeatureConfig:
    name: str
    params: dict = field(default_factory=dict)
    # No separate 'windows' field

# Then:
config.params = {'windows': [10, 20]}  # For Type A
config.params = {'window': 14}         # For Type B
```

**Option 2: Remove general `windows` shortcut**
```python
# Always use feature-specific
calculate(df,
    features=['moving_average', 'volatility'],
    moving_average_windows=[10, 20],
    volatility_windows=[10, 20]
)
# More explicit, no magic behavior
```

**Option 3: Unify to always use `windows` (plural)**
```python
# Even for single-window features
calculate(df, features=['rsi'], rsi_windows=[14])  # List with one element
# More consistent, but less intuitive
```

## Recommendation for Users

**When in doubt, use feature-specific parameters:**
```python
calculate(df,
    features=['moving_average', 'rsi', 'bollinger'],
    moving_average_windows=[10, 50, 200],  # Explicit
    rsi_window=21,                         # Explicit
    bollinger_window=20                    # Explicit
)
```

This is more verbose but **completely clear** about what goes where.
