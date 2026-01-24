"""
Alpha weight models for combining multiple alpha signals.

Provides extensible framework for computing alpha weights dynamically.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeightResult:
    """Result of weight computation."""

    weights: dict[str, float]  # alpha_name -> weight
    metadata: dict = field(default_factory=dict)  # Additional info (e.g., ICs, optimization stats)

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    def get_weight(self, alpha_name: str) -> float:
        """Get weight for a specific alpha."""
        return self.weights.get(alpha_name, 0.0)


class AlphaWeightModel(ABC):
    """
    Abstract base class for alpha weight computation.

    Implementations determine how to combine multiple alpha signals
    into a single composite alpha score.

    Example:
        model = EqualWeightModel()
        result = model.compute_weights(["momentum_20d", "mean_reversion"])
        # result.weights = {"momentum_20d": 0.5, "mean_reversion": 0.5}
    """

    @abstractmethod
    def compute_weights(
        self,
        alpha_names: list[str],
        historical_alphas: Optional[dict] = None,
        returns: Optional[dict] = None,
    ) -> WeightResult:
        """
        Compute weights for given alphas.

        Args:
            alpha_names: List of alpha signal names to weight
            historical_alphas: Optional historical alpha values for IC calculation
                              Format: {alpha_name: {date: {symbol: value}}}
            returns: Optional historical returns for IC calculation
                    Format: {date: {symbol: return}}

        Returns:
            WeightResult with computed weights
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name for logging/display."""
        pass

    def validate_alphas(self, alpha_names: list[str]) -> None:
        """Validate alpha names are not empty."""
        if not alpha_names:
            raise ValueError("At least one alpha required for weight computation")


class EqualWeightModel(AlphaWeightModel):
    """
    Equal weight allocation across all alphas.

    Simple baseline model that assigns 1/N weight to each alpha.

    Example:
        model = EqualWeightModel()
        result = model.compute_weights(["momentum", "value", "quality"])
        # weights = {"momentum": 0.333, "value": 0.333, "quality": 0.333}
    """

    @property
    def name(self) -> str:
        return "equal_weight"

    def compute_weights(
        self,
        alpha_names: list[str],
        historical_alphas: Optional[dict] = None,
        returns: Optional[dict] = None,
    ) -> WeightResult:
        """Assign equal weight to each alpha."""
        self.validate_alphas(alpha_names)

        n = len(alpha_names)
        weight = 1.0 / n
        weights = {name: weight for name in alpha_names}

        logger.debug(f"EqualWeightModel: {n} alphas, weight={weight:.4f} each")

        return WeightResult(
            weights=weights,
            metadata={"model": self.name, "n_alphas": n},
        )


class FixedWeightModel(AlphaWeightModel):
    """
    Fixed user-specified weights.

    Wraps static weights from configuration into the AlphaWeightModel interface.

    Example:
        model = FixedWeightModel({"momentum": 0.6, "value": 0.4})
        result = model.compute_weights(["momentum", "value"])
    """

    def __init__(self, weights: dict[str, float]):
        """
        Initialize with fixed weights.

        Args:
            weights: Dict mapping alpha names to weights (must sum to 1.0)
        """
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        self._weights = weights.copy()

    @property
    def name(self) -> str:
        return "fixed_weight"

    def compute_weights(
        self,
        alpha_names: list[str],
        historical_alphas: Optional[dict] = None,
        returns: Optional[dict] = None,
    ) -> WeightResult:
        """Return fixed weights for requested alphas."""
        self.validate_alphas(alpha_names)

        # Validate all requested alphas have weights
        missing = [a for a in alpha_names if a not in self._weights]
        if missing:
            raise ValueError(f"No weights specified for alphas: {missing}")

        # Extract only requested alphas and renormalize
        weights = {name: self._weights[name] for name in alpha_names}
        total = sum(weights.values())

        if abs(total - 1.0) > 1e-6:
            # Renormalize if subset doesn't sum to 1
            weights = {k: v / total for k, v in weights.items()}
            logger.debug("FixedWeightModel: renormalized weights to sum to 1.0")

        return WeightResult(
            weights=weights,
            metadata={"model": self.name, "original_weights": self._weights},
        )


class ICWeightModel(AlphaWeightModel):
    """
    Information Coefficient (IC) based weighting.

    Weights alphas proportionally to their predictive power (IC).
    Placeholder for future implementation.

    IC = correlation between alpha signal and forward returns.
    Higher IC = more predictive = higher weight.
    """

    def __init__(self, lookback_days: int = 60, min_ic: float = 0.0):
        """
        Initialize IC weight model.

        Args:
            lookback_days: Days of history for IC calculation
            min_ic: Minimum IC threshold (alphas below this get 0 weight)
        """
        self.lookback_days = lookback_days
        self.min_ic = min_ic

    @property
    def name(self) -> str:
        return "ic_weight"

    def compute_weights(
        self,
        alpha_names: list[str],
        historical_alphas: Optional[dict] = None,
        returns: Optional[dict] = None,
    ) -> WeightResult:
        """
        Compute IC-based weights.

        Requires historical_alphas and returns to calculate ICs.
        Falls back to equal weight if data not provided.
        """
        self.validate_alphas(alpha_names)

        if historical_alphas is None or returns is None:
            logger.warning("ICWeightModel: No historical data, falling back to equal weight")
            return EqualWeightModel().compute_weights(alpha_names)

        # Calculate IC for each alpha
        ics = {}
        for alpha_name in alpha_names:
            ic = self._calculate_ic(
                historical_alphas.get(alpha_name, {}),
                returns,
            )
            ics[alpha_name] = ic

        logger.debug(f"ICWeightModel: calculated ICs = {ics}")

        # Filter by min_ic threshold
        valid_ics = {k: max(v, 0) for k, v in ics.items() if v >= self.min_ic}

        if not valid_ics:
            logger.warning("ICWeightModel: No alphas above IC threshold, using equal weight")
            return EqualWeightModel().compute_weights(alpha_names)

        # Normalize to weights
        total_ic = sum(valid_ics.values())
        if total_ic == 0:
            return EqualWeightModel().compute_weights(alpha_names)

        weights = {}
        for name in alpha_names:
            if name in valid_ics:
                weights[name] = valid_ics[name] / total_ic
            else:
                weights[name] = 0.0

        # Renormalize to ensure sum = 1
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return WeightResult(
            weights=weights,
            metadata={
                "model": self.name,
                "ics": ics,
                "lookback_days": self.lookback_days,
                "min_ic": self.min_ic,
            },
        )

    def _calculate_ic(
        self,
        alpha_values: dict,
        returns: dict,
    ) -> float:
        """
        Calculate Information Coefficient for an alpha.

        IC = rank correlation between alpha and forward returns.

        Args:
            alpha_values: {date: {symbol: alpha_value}}
            returns: {date: {symbol: return}}

        Returns:
            IC value (typically -1 to 1)
        """
        # Placeholder - actual implementation would compute Spearman correlation
        # between alpha ranks and forward return ranks
        #
        # For now, return 0 (equal weight fallback)
        # TODO: Implement proper IC calculation
        return 0.0


class OptimizedWeightModel(AlphaWeightModel):
    """
    Mean-variance optimized weights.

    Optimizes weights to maximize Sharpe ratio of combined alpha.
    Placeholder for future implementation.
    """

    def __init__(
        self,
        lookback_days: int = 252,
        regularization: float = 0.1,
    ):
        """
        Initialize optimized weight model.

        Args:
            lookback_days: Days of history for optimization
            regularization: L2 regularization to prevent extreme weights
        """
        self.lookback_days = lookback_days
        self.regularization = regularization

    @property
    def name(self) -> str:
        return "optimized_weight"

    def compute_weights(
        self,
        alpha_names: list[str],
        historical_alphas: Optional[dict] = None,
        returns: Optional[dict] = None,
    ) -> WeightResult:
        """
        Compute optimized weights.

        Falls back to equal weight if insufficient data.
        """
        self.validate_alphas(alpha_names)

        if historical_alphas is None or returns is None:
            logger.warning("OptimizedWeightModel: No historical data, falling back to equal weight")
            return EqualWeightModel().compute_weights(alpha_names)

        # Placeholder - actual implementation would:
        # 1. Calculate alpha covariance matrix
        # 2. Calculate expected alpha returns (ICs)
        # 3. Solve quadratic optimization for max Sharpe
        #
        # TODO: Implement proper optimization
        logger.warning("OptimizedWeightModel: Not yet implemented, using equal weight")
        return EqualWeightModel().compute_weights(alpha_names)


def create_weight_model(
    model_type: str,
    config: Optional[dict] = None,
) -> AlphaWeightModel:
    """
    Factory function to create weight models.

    Args:
        model_type: One of "equal", "fixed", "ic", "optimized"
        config: Model-specific configuration

    Returns:
        AlphaWeightModel instance
    """
    config = config or {}

    if model_type == "equal":
        return EqualWeightModel()

    elif model_type == "fixed":
        weights = config.get("weights")
        if not weights:
            raise ValueError("FixedWeightModel requires 'weights' in config")
        return FixedWeightModel(weights)

    elif model_type == "ic":
        return ICWeightModel(
            lookback_days=config.get("lookback_days", 60),
            min_ic=config.get("min_ic", 0.0),
        )

    elif model_type == "optimized":
        return OptimizedWeightModel(
            lookback_days=config.get("lookback_days", 252),
            regularization=config.get("regularization", 0.1),
        )

    else:
        raise ValueError(f"Unknown weight model type: {model_type}")
