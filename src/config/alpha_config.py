"""
YAML configuration support for alpha strategies.
"""

from pathlib import Path
import yaml

from strategy.alpha_strategy import AlphaStrategyConfig


def load_alpha_config(path: str | Path) -> AlphaStrategyConfig:
    """
    Load AlphaStrategyConfig from YAML file.

    Expected YAML format:
        strategy:
          type: alpha
          alphas:
            - momentum_20d
            - mean_reversion
          thresholds:
            long: 0.5
            short: -0.5
          refresh: daily
          max_positions: 10

    Args:
        path: Path to YAML config file

    Returns:
        AlphaStrategyConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw_config = yaml.safe_load(f)

    return parse_alpha_config(raw_config)


def parse_alpha_config(raw_config: dict) -> AlphaStrategyConfig:
    """
    Parse raw config dict into AlphaStrategyConfig.

    Args:
        raw_config: Raw configuration dictionary

    Returns:
        AlphaStrategyConfig instance

    Raises:
        ValueError: If config is invalid
    """
    # Extract strategy section
    if "strategy" in raw_config:
        config = raw_config["strategy"]
    else:
        config = raw_config

    # Validate type if present
    if "type" in config and config["type"] != "alpha":
        raise ValueError(f"Invalid strategy type: {config['type']}")

    # Extract fields
    alphas = config.get("alphas", ["momentum_20d"])
    thresholds = config.get("thresholds", {})
    refresh = config.get("refresh", "daily")
    max_positions = config.get("max_positions", 10)

    # Validate
    _validate_config(alphas, thresholds, refresh, max_positions)

    return AlphaStrategyConfig(
        alpha_names=alphas,
        long_threshold=thresholds.get("long", 0.5),
        short_threshold=thresholds.get("short", -0.5),
        refresh_frequency=refresh,
        max_positions=max_positions,
    )


def _validate_config(
    alphas: list[str],
    thresholds: dict[str, float],
    refresh: str,
    max_positions: int,
) -> None:
    """
    Validate configuration values.

    Raises:
        ValueError: If validation fails
    """
    if not alphas:
        raise ValueError("At least one alpha must be specified")

    long_threshold = thresholds.get("long", 0.5)
    short_threshold = thresholds.get("short", -0.5)

    if long_threshold <= short_threshold:
        raise ValueError(
            f"long_threshold ({long_threshold}) must be > short_threshold ({short_threshold})"
        )

    valid_refresh = {"daily", "hourly"}
    if refresh not in valid_refresh:
        raise ValueError(
            f"Invalid refresh frequency: {refresh}. Must be one of {valid_refresh}"
        )

    if max_positions < 1:
        raise ValueError(f"max_positions must be >= 1, got {max_positions}")


def save_alpha_config(config: AlphaStrategyConfig, path: str | Path) -> None:
    """
    Save AlphaStrategyConfig to YAML file.

    Args:
        config: Configuration to save
        path: Output file path
    """
    path = Path(path)

    yaml_config = {
        "strategy": {
            "type": "alpha",
            "alphas": config.alpha_names,
            "thresholds": {
                "long": config.long_threshold,
                "short": config.short_threshold,
            },
            "refresh": config.refresh_frequency,
            "max_positions": config.max_positions,
        }
    }

    with open(path, "w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False)
