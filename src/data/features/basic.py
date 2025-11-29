from typing import Optional, Dict
import pandas as pd
import numpy as np
from models import FeatureConfig, ColumnMapping


class BasicFeatures:
    """
    Basic feature groups with their default configurations.

    Feature Groups:
        1. returns: ['returns', 'log_returns']
        2. price_change: ['price_change', 'high_low_spread', 'open_close_spread']
        3. moving_average: ['sma_{window}', 'ema_{window}']
        4. volatility: ['volatility_{window}']
        5. volume: ['volume_change', 'volume_sma_{window}', 'volume_ratio']
        6. bollinger: ['bb_middle', 'bb_upper', 'bb_lower', 'bb_width', 'bb_position']
        7. rsi: ['rsi']
        8. macd: ['macd', 'macd_signal', 'macd_histogram']
        9. momentum: ['momentum_{window}', 'roc_{window}']
        10. atr: ['atr']
    """
    # Feature group names
    RETURNS = "returns"
    PRICE_CHANGE = "price_change"
    MOVING_AVERAGE = "moving_average"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    BOLLINGER = "bollinger"
    RSI = "rsi"
    MACD = "macd"
    MOMENTUM = "momentum"
    ATR = "atr"

    # Default configurations for each feature group
    DEFAULT_CONFIGS: Dict[str, FeatureConfig] = {
        RETURNS: FeatureConfig(
            name=RETURNS,
        ),
        PRICE_CHANGE: FeatureConfig(
            name=PRICE_CHANGE,
        ),
        MOVING_AVERAGE: FeatureConfig(
            name=MOVING_AVERAGE,
            windows=[5, 10, 20],
        ),
        VOLATILITY: FeatureConfig(
            name=VOLATILITY,
            windows=[5, 10, 20],
        ),
        VOLUME: FeatureConfig(
            name=VOLUME,
            params={'volume_sma_window': 20},
        ),
        BOLLINGER: FeatureConfig(
            name=BOLLINGER,
            params={'window': 20, 'num_std': 2},
        ),
        RSI: FeatureConfig(
            name=RSI,
            params={'window': 14},
        ),
        MACD: FeatureConfig(
            name=MACD,
            params={'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
        ),
        MOMENTUM: FeatureConfig(
            name=MOMENTUM,
            windows=[5, 10, 20],
        ),
        ATR: FeatureConfig(
            name=ATR,
            params={'window': 14},
        ),
    }

    @classmethod
    def get_config(cls, feature_name: str, **kwargs) -> FeatureConfig:
        """
        Get configuration for a feature group with optional parameter overrides.

        Args:
            feature_name: Name of the feature group
            **kwargs: Optional parameter overrides (e.g., windows=[10, 20], window=30)

        Returns:
            FeatureConfig with default or custom parameters
        """
        if feature_name not in cls.DEFAULT_CONFIGS:
            raise ValueError(f"Unknown feature: {feature_name}")

        # Get default config
        default_config = cls.DEFAULT_CONFIGS[feature_name]

        # Create a new config with overrides
        # Put general `windows` in the right place
        windows = kwargs.pop('windows', default_config.windows)
        params = {**default_config.params, **kwargs}

        return FeatureConfig(
            name=feature_name,
            windows=windows,
            params=params
        )

    @classmethod
    def get_default_params(cls, feature_name: str) -> dict:
        """
        Get the default parameters for a feature group.

        Args:
            feature_name: Name of the feature group

        Returns:
            Dictionary containing default parameters (windows and/or params)
        """
        if feature_name not in cls.DEFAULT_CONFIGS:
            raise ValueError(f"Unknown feature: {feature_name}")

        config = cls.DEFAULT_CONFIGS[feature_name]
        result = {}

        if config.windows is not None:
            result['windows'] = config.windows
        if config.params:
            result.update(config.params)

        return result

    @classmethod
    def list_features(cls) -> list[str]:
        """List all available feature groups."""
        return list(cls.DEFAULT_CONFIGS.keys())

    @classmethod
    def calculate(
        cls,
        df: pd.DataFrame,
        features: list[str],
        col_mapping: Optional[ColumnMapping] = None,
        **feature_kwargs
    ) -> pd.DataFrame:
        """
        Calculate specified features on a DataFrame.

        Args:
            df: Input DataFrame (will be copied, not modified in place)
            features: List of feature group names to calculate
            col_mapping: Column name mapping (uses defaults if None)
            **feature_kwargs: Override parameters for specific features
                Example: windows=[10,20], rsi_window=21, bollinger_window=30

        Returns:
            DataFrame with calculated features added
        """
        if col_mapping is None:
            col_mapping = ColumnMapping()

        df_result = df.copy()

        for feature in features:
            if feature not in cls.DEFAULT_CONFIGS:
                raise ValueError(f"Unknown feature: {feature}")

            # Get feature-specific kwargs (e.g., 'rsi_window' -> 'window' for RSI)
            feature_prefix = f"{feature}_"
            specific_kwargs = {
                k.replace(feature_prefix, ''): v
                for k, v in feature_kwargs.items()
                if k.startswith(feature_prefix)
            }

            # Also check for general 'windows' parameter
            if 'windows' in feature_kwargs and feature in [cls.MOVING_AVERAGE, cls.VOLATILITY, cls.MOMENTUM]:
                specific_kwargs['windows'] = feature_kwargs['windows']

            # Get config with overrides
            config = cls.get_config(feature, **specific_kwargs)

            # Call the appropriate calculation method
            method_name = f'_calc_{feature}'
            if hasattr(cls, method_name):
                method = getattr(cls, method_name)
                method(df_result, config, col_mapping)
            else:
                raise NotImplementedError(f"Calculation method {method_name} not implemented")

        return df_result

    @staticmethod
    def _calc_returns(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate returns features."""
        df['returns'] = df[cols.close].pct_change()
        df['log_returns'] = np.log(df[cols.close] / df[cols.close].shift(1))

    @staticmethod
    def _calc_price_change(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate price change features."""
        df['price_change'] = df[cols.close].diff()
        df['high_low_spread'] = df[cols.high] - df[cols.low]
        df['open_close_spread'] = df[cols.close] - df[cols.open]

    @staticmethod
    def _calc_moving_average(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate moving average features."""
        if config.windows is None:
            raise ValueError("Moving average requires 'windows' parameter")

        for window in config.windows:
            df[f'sma_{window}'] = df[cols.close].rolling(window=window).mean()
            df[f'ema_{window}'] = df[cols.close].ewm(span=window, adjust=False).mean()

    @staticmethod
    def _calc_volatility(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate volatility features."""
        if config.windows is None:
            raise ValueError("Volatility requires 'windows' parameter")

        # Ensure returns exists
        if 'returns' not in df.columns:
            df['returns'] = df[cols.close].pct_change()

        for window in config.windows:
            df[f'volatility_{window}'] = df['returns'].rolling(window=window).std()

    @staticmethod
    def _calc_volume(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate volume features."""
        volume_sma_window = config.params.get('volume_sma_window', 20)

        df['volume_change'] = df[cols.volume].pct_change()
        df[f'volume_sma_{volume_sma_window}'] = df[cols.volume].rolling(window=volume_sma_window).mean()
        df['volume_ratio'] = df[cols.volume] / df[f'volume_sma_{volume_sma_window}']

    @staticmethod
    def _calc_bollinger(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate Bollinger Bands features."""
        window = config.params.get('window', 20)
        num_std = config.params.get('num_std', 2)

        df['bb_middle'] = df[cols.close].rolling(window=window).mean()
        rolling_std = df[cols.close].rolling(window=window).std()
        df['bb_upper'] = df['bb_middle'] + (rolling_std * num_std)
        df['bb_lower'] = df['bb_middle'] - (rolling_std * num_std)
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = (df[cols.close] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    @staticmethod
    def _calc_rsi(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate RSI (Relative Strength Index)."""
        window = config.params.get('window', 14)

        delta = df[cols.close].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

    @staticmethod
    def _calc_macd(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        fast_period = config.params.get('fast_period', 12)
        slow_period = config.params.get('slow_period', 26)
        signal_period = config.params.get('signal_period', 9)

        exp1 = df[cols.close].ewm(span=fast_period, adjust=False).mean()
        exp2 = df[cols.close].ewm(span=slow_period, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=signal_period, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

    @staticmethod
    def _calc_momentum(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate momentum features."""
        if config.windows is None:
            raise ValueError("Momentum requires 'windows' parameter")

        for window in config.windows:
            df[f'momentum_{window}'] = df[cols.close] - df[cols.close].shift(window)
            df[f'roc_{window}'] = ((df[cols.close] - df[cols.close].shift(window)) /
                                    df[cols.close].shift(window)) * 100

    @staticmethod
    def _calc_atr(df: pd.DataFrame, config: FeatureConfig, cols: ColumnMapping) -> None:
        """Calculate ATR (Average True Range)."""
        window = config.params.get('window', 14)

        high_low = df[cols.high] - df[cols.low]
        high_close = np.abs(df[cols.high] - df[cols.close].shift(1))
        low_close = np.abs(df[cols.low] - df[cols.close].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=window).mean()


if __name__ == '__main__':
    # Example 1: List all features
    print("Available features:", BasicFeatures.list_features())
    print()

    # Example 2: Get default parameters
    print("RSI defaults:", BasicFeatures.get_default_params('rsi'))
    print("MACD defaults:", BasicFeatures.get_default_params('macd'))
    print()

    from data.preprocessing import Preprocessor, YF_DATA_PATH
    df = Preprocessor(YF_DATA_PATH / "AAPL.csv").load().clean()

    # Example 3: Using with default column names (Open, High, Low, Close, Volume)
    # Assuming you have a DataFrame df with standard Yahoo Finance columns
    df_with_features = BasicFeatures.calculate(
        df,
        features=['returns', 'rsi', 'moving_average'],
        windows=[10, 50, 200],  # Custom MA windows
        rsi_window=21           # Custom RSI window
    )

    print(df_with_features)

