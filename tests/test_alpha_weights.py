"""
Tests for alpha weight models.
"""

import pytest

from strategy.alpha_weights import (
    AlphaWeightModel,
    EqualWeightModel,
    WeightResult,
)


class TestWeightResult:
    """Tests for WeightResult dataclass."""

    def test_valid_weights(self):
        """Test WeightResult with valid weights."""
        result = WeightResult(
            weights={"alpha1": 0.5, "alpha2": 0.5},
            metadata={"test": True},
        )
        assert result.weights["alpha1"] == 0.5
        assert result.get_weight("alpha1") == 0.5
        assert result.get_weight("unknown") == 0.0

    def test_invalid_weights_sum(self):
        """Test WeightResult rejects weights not summing to 1."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            WeightResult(weights={"alpha1": 0.3, "alpha2": 0.3})

    def test_weights_tolerance(self):
        """Test WeightResult accepts small floating point errors."""
        result = WeightResult(
            weights={"a": 0.333333, "b": 0.333333, "c": 0.333334}
        )
        assert sum(result.weights.values()) == pytest.approx(1.0)


class TestEqualWeightModel:
    """Tests for EqualWeightModel."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return EqualWeightModel()

    def test_name(self, model):
        """Test model name."""
        assert model.name == "equal_weight"

    def test_single_alpha(self, model):
        """Test with single alpha."""
        result = model.compute_weights(["momentum"])
        assert result.weights == {"momentum": 1.0}

    def test_two_alphas(self, model):
        """Test with two alphas."""
        result = model.compute_weights(["momentum", "value"])
        assert result.weights["momentum"] == 0.5
        assert result.weights["value"] == 0.5

    def test_three_alphas(self, model):
        """Test with three alphas."""
        result = model.compute_weights(["a", "b", "c"])
        assert result.weights["a"] == pytest.approx(1 / 3)
        assert result.weights["b"] == pytest.approx(1 / 3)
        assert result.weights["c"] == pytest.approx(1 / 3)

    def test_empty_alphas_raises(self, model):
        """Test empty alphas raises error."""
        with pytest.raises(ValueError, match="At least one alpha"):
            model.compute_weights([])

    def test_metadata_included(self, model):
        """Test metadata is populated."""
        result = model.compute_weights(["a", "b"])
        assert result.metadata["model"] == "equal_weight"
        assert result.metadata["n_alphas"] == 2


class TestAlphaWeightModelABC:
    """Tests for ABC interface."""

    def test_cannot_instantiate_abc(self):
        """Test ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AlphaWeightModel()

    def test_subclass_must_implement_compute_weights(self):
        """Test subclass must implement compute_weights."""

        class IncompleteModel(AlphaWeightModel):
            @property
            def name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_subclass_must_implement_name(self):
        """Test subclass must implement name property."""

        class IncompleteModel(AlphaWeightModel):
            def compute_weights(self, alpha_names):
                return WeightResult(weights={"a": 1.0})

        with pytest.raises(TypeError):
            IncompleteModel()
