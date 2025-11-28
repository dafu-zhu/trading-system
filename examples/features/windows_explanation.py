"""
Clear explanation of 'windows' parameter design in BasicFeatures.
"""
import pandas as pd
import numpy as np
from src.data.features.basic import BasicFeatures

# Create simple test data
np.random.seed(42)
df = pd.DataFrame({
    'Open': np.random.randn(50) + 100,
    'High': np.random.randn(50) + 101,
    'Low': np.random.randn(50) + 99,
    'Close': np.random.randn(50) + 100,
    'Volume': np.random.randint(1000, 10000, 50)
})

print("=" * 80)
print("UNDERSTANDING 'windows' vs 'window' PARAMETERS")
print("=" * 80)

# ============================================================================
# Case 1: General 'windows' parameter (applies to MA, volatility, momentum)
# ============================================================================
print("\n" + "-" * 80)
print("Case 1: General 'windows' parameter")
print("-" * 80)
print("Code: calculate(df, features=['moving_average'], windows=[5, 10])")

df1 = BasicFeatures.calculate(df, features=['moving_average'], windows=[5, 10])
ma_cols = [col for col in df1.columns if 'sma' in col or 'ema' in col]
print(f"Columns created: {ma_cols}")
print("Expected: ['sma_5', 'ema_5', 'sma_10', 'ema_10']")

# ============================================================================
# Case 2: Feature-specific 'windows' parameter
# ============================================================================
print("\n" + "-" * 80)
print("Case 2: Feature-specific 'windows' parameter")
print("-" * 80)
print("Code: calculate(df, features=['moving_average'], moving_average_windows=[20, 50])")

df2 = BasicFeatures.calculate(df, features=['moving_average'], moving_average_windows=[20, 50])
ma_cols = [col for col in df2.columns if 'sma' in col or 'ema' in col]
print(f"Columns created: {ma_cols}")
print("Expected: ['sma_20', 'ema_20', 'sma_50', 'ema_50']")

# ============================================================================
# Case 3: General 'windows' with multiple Type A features
# ============================================================================
print("\n" + "-" * 80)
print("Case 3: General 'windows' applies to ALL Type A features")
print("-" * 80)
print("Code: calculate(df, features=['moving_average', 'volatility', 'momentum'], windows=[10, 20])")

df3 = BasicFeatures.calculate(
    df,
    features=['moving_average', 'volatility', 'momentum'],
    windows=[10, 20]
)
ma_cols = [col for col in df3.columns if 'sma' in col or 'ema' in col]
vol_cols = [col for col in df3.columns if 'volatility' in col]
mom_cols = [col for col in df3.columns if 'momentum' in col or 'roc' in col]
print(f"MA columns: {ma_cols}")
print(f"Volatility columns: {vol_cols}")
print(f"Momentum columns: {mom_cols}")
print("All use windows=[10, 20]")

# ============================================================================
# Case 4: Different windows for different features
# ============================================================================
print("\n" + "-" * 80)
print("Case 4: Different windows for different Type A features")
print("-" * 80)
print("""Code: calculate(df,
    features=['moving_average', 'volatility'],
    moving_average_windows=[50, 200],
    volatility_windows=[5, 10]
)""")

df4 = BasicFeatures.calculate(
    df,
    features=['moving_average', 'volatility'],
    moving_average_windows=[50, 200],  # MA gets [50, 200]
    volatility_windows=[5, 10]         # Volatility gets [5, 10]
)
ma_cols = [col for col in df4.columns if 'sma' in col or 'ema' in col]
vol_cols = [col for col in df4.columns if 'volatility' in col]
print(f"MA columns: {ma_cols}")
print(f"Volatility columns: {vol_cols}")

# ============================================================================
# Case 5: Type B features use 'window' (singular)
# ============================================================================
print("\n" + "-" * 80)
print("Case 5: Type B features use 'window' (singular)")
print("-" * 80)
print("Code: calculate(df, features=['rsi', 'atr'], rsi_window=21, atr_window=14)")

df5 = BasicFeatures.calculate(
    df,
    features=['rsi', 'atr'],
    rsi_window=21,
    atr_window=14
)
type_b_cols = [col for col in df5.columns if col in ['rsi', 'atr']]
print(f"Columns created: {type_b_cols}")
print("Expected: ['rsi', 'atr'] - only ONE column each")

# Check the configs
rsi_config = BasicFeatures.get_config('rsi', window=21)
print(f"\nRSI config: {rsi_config}")
print(f"  - windows: {rsi_config.windows} (None)")
print(f"  - params: {rsi_config.params} (contains 'window')")

# ============================================================================
# Case 6: What happens if you use 'windows' with Type B features?
# ============================================================================
print("\n" + "-" * 80)
print("Case 6: Using 'windows' (plural) with Type B features - NO EFFECT")
print("-" * 80)
print("Code: calculate(df, features=['rsi'], windows=[10, 20])  # WRONG!")

df6 = BasicFeatures.calculate(df, features=['rsi'], windows=[10, 20])
# Check if RSI was calculated
if 'rsi' in df6.columns:
    print("RSI column exists: YES")
    # Check what window was used (should be default 14)
    print("Used default window=14 because 'windows' doesn't apply to RSI")
else:
    print("RSI column exists: NO")

print("\nWhy? Because line 204 in calculate():")
print("if 'windows' in kwargs and feature in [MOVING_AVERAGE, VOLATILITY, MOMENTUM]")
print("                                       ^^^ RSI is NOT in this list!")

# ============================================================================
# Case 7: Correct way for Type B features
# ============================================================================
print("\n" + "-" * 80)
print("Case 7: CORRECT way to set window for Type B features")
print("-" * 80)
print("Code: calculate(df, features=['rsi'], rsi_window=21)  # CORRECT!")

df7 = BasicFeatures.calculate(df, features=['rsi'], rsi_window=21)
print("RSI column exists:", 'rsi' in df7.columns)
print("Used custom window=21")

# ============================================================================
# SUMMARY TABLE
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY: How to specify windows/window")
print("=" * 80)

summary = """
┌─────────────────────┬──────────────┬────────────────────────────────────┐
│ Feature             │ Parameter    │ Example                            │
├─────────────────────┼──────────────┼────────────────────────────────────┤
│ moving_average      │ windows      │ windows=[10,20]                    │
│                     │ (plural)     │ OR moving_average_windows=[10,20]  │
├─────────────────────┼──────────────┼────────────────────────────────────┤
│ volatility          │ windows      │ windows=[10,20]                    │
│                     │ (plural)     │ OR volatility_windows=[10,20]      │
├─────────────────────┼──────────────┼────────────────────────────────────┤
│ momentum            │ windows      │ windows=[10,20]                    │
│                     │ (plural)     │ OR momentum_windows=[10,20]        │
├─────────────────────┼──────────────┼────────────────────────────────────┤
│ rsi                 │ window       │ rsi_window=21                      │
│                     │ (singular)   │ NOT windows! ✗                     │
├─────────────────────┼──────────────┼────────────────────────────────────┤
│ atr                 │ window       │ atr_window=14                      │
│                     │ (singular)   │ NOT windows! ✗                     │
├─────────────────────┼──────────────┼────────────────────────────────────┤
│ bollinger           │ window       │ bollinger_window=20                │
│                     │ (singular)   │ NOT windows! ✗                     │
└─────────────────────┴──────────────┴────────────────────────────────────┘

KEY RULES:
1. General 'windows=[10,20]' ONLY affects: moving_average, volatility, momentum
2. For other features, use feature-specific parameters with singular 'window'
3. Feature-specific always overrides general
"""
print(summary)

# ============================================================================
# get_default_params() behavior
# ============================================================================
print("\n" + "=" * 80)
print("How get_default_params() returns windows")
print("=" * 80)

features_to_check = ['moving_average', 'volatility', 'momentum', 'rsi', 'atr', 'bollinger']
for feature in features_to_check:
    params = BasicFeatures.get_default_params(feature)
    print(f"\n{feature}:")
    print(f"  {params}")
    if 'windows' in params:
        print(f"  → Has 'windows' (plural) - Type A feature")
    elif 'window' in params:
        print(f"  → Has 'window' (singular) - Type B feature")
    else:
        print(f"  → No window parameter")
