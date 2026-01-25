"""
Alpha weight models for combining multiple alpha signals.

Provides extensible framework for computing alpha weights dynamically.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeightResult:
    """Result of weight computation."""

    weights: dict[str, float]  # alpha_name -> weight
    metadata: dict = field(default_factory=dict)

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

    Example:
        model = EqualWeightModel()
        result = model.compute_weights(["momentum_20d", "mean_reversion"])
        # result.weights = {"momentum_20d": 0.5, "mean_reversion": 0.5}
    """

    @abstractmethod
    def compute_weights(self, alpha_names: list[str]) -> WeightResult:
        """
        Compute weights for given alphas.

        Args:
            alpha_names: List of alpha signal names to weight

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

    Assigns 1/N weight to each alpha.

    Example:
        model = EqualWeightModel()
        result = model.compute_weights(["momentum", "value", "quality"])
        # weights = {"momentum": 0.333, "value": 0.333, "quality": 0.333}
    """

    @property
    def name(self) -> str:
        return "equal_weight"

    def compute_weights(self, alpha_names: list[str]) -> WeightResult:
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
