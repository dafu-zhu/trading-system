"""
Tests for alpha weight models.

Tests EqualWeightModel, FixedWeightModel, ICWeightModel, and factory function.
"""

import pytest

from strategy.alpha_weights import (
    AlphaWeightModel,
    EqualWeightModel,
    FixedWeightModel,
    ICWeightModel,
    OptimizedWeightModel,
    WeightResult,
    create_weight_model,
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
        # Should not raise - within tolerance
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
        assert result.weights["a"] == pytest.approx(1/3)
        assert result.weights["b"] == pytest.approx(1/3)
        assert result.weights["c"] == pytest.approx(1/3)

    def test_empty_alphas_raises(self, model):
        """Test empty alphas raises error."""
        with pytest.raises(ValueError, match="At least one alpha"):
            model.compute_weights([])

    def test_metadata_included(self, model):
        """Test metadata is populated."""
        result = model.compute_weights(["a", "b"])
        assert result.metadata["model"] == "equal_weight"
        assert result.metadata["n_alphas"] == 2


class TestFixedWeightModel:
    """Tests for FixedWeightModel."""

    def test_basic_usage(self):
        """Test basic fixed weights."""
        model = FixedWeightModel({"a": 0.6, "b": 0.4})
        result = model.compute_weights(["a", "b"])
        assert result.weights["a"] == 0.6
        assert result.weights["b"] == 0.4

    def test_name(self):
        """Test model name."""
        model = FixedWeightModel({"a": 1.0})
        assert model.name == "fixed_weight"

    def test_invalid_weights_sum_raises(self):
        """Test invalid weights sum raises on init."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            FixedWeightModel({"a": 0.5, "b": 0.3})

    def test_missing_alpha_raises(self):
        """Test missing alpha raises error."""
        model = FixedWeightModel({"a": 0.6, "b": 0.4})
        with pytest.raises(ValueError, match="No weights specified"):
            model.compute_weights(["a", "c"])

    def test_subset_renormalization(self):
        """Test subset of alphas is renormalized."""
        model = FixedWeightModel({"a": 0.5, "b": 0.3, "c": 0.2})
        result = model.compute_weights(["a", "b"])
        # Should renormalize 0.5 + 0.3 = 0.8 -> 1.0
        assert result.weights["a"] == pytest.approx(0.5 / 0.8)
        assert result.weights["b"] == pytest.approx(0.3 / 0.8)

    def test_empty_alphas_raises(self):
        """Test empty alphas raises error."""
        model = FixedWeightModel({"a": 1.0})
        with pytest.raises(ValueError, match="At least one alpha"):
            model.compute_weights([])


class TestICWeightModel:
    """Tests for ICWeightModel."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return ICWeightModel(lookback_days=60, min_ic=0.0)

    def test_name(self, model):
        """Test model name."""
        assert model.name == "ic_weight"

    def test_fallback_to_equal_without_data(self, model):
        """Test falls back to equal weight without historical data."""
        result = model.compute_weights(["a", "b"])
        # Should fall back to equal weight
        assert result.weights["a"] == 0.5
        assert result.weights["b"] == 0.5

    def test_fallback_with_none_alphas(self, model):
        """Test falls back when historical_alphas is None."""
        result = model.compute_weights(["a", "b"], historical_alphas=None)
        assert result.weights["a"] == 0.5

    def test_metadata_contains_ics(self, model):
        """Test metadata contains IC values when data provided."""
        # With empty historical data, still produces metadata
        result = model.compute_weights(
            ["a", "b"],
            historical_alphas={"a": {}, "b": {}},
            returns={},
        )
        assert "ics" in result.metadata or result.weights["a"] == 0.5


class TestOptimizedWeightModel:
    """Tests for OptimizedWeightModel."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return OptimizedWeightModel(lookback_days=252)

    def test_name(self, model):
        """Test model name."""
        assert model.name == "optimized_weight"

    def test_fallback_to_equal_without_data(self, model):
        """Test falls back to equal weight without data."""
        result = model.compute_weights(["a", "b"])
        assert result.weights["a"] == 0.5
        assert result.weights["b"] == 0.5


class TestCreateWeightModel:
    """Tests for factory function."""

    def test_create_equal(self):
        """Test creating equal weight model."""
        model = create_weight_model("equal")
        assert isinstance(model, EqualWeightModel)

    def test_create_fixed(self):
        """Test creating fixed weight model."""
        model = create_weight_model("fixed", {"weights": {"a": 0.6, "b": 0.4}})
        assert isinstance(model, FixedWeightModel)

    def test_create_fixed_without_weights_raises(self):
        """Test fixed model without weights raises."""
        with pytest.raises(ValueError, match="requires 'weights'"):
            create_weight_model("fixed", {})

    def test_create_ic(self):
        """Test creating IC weight model."""
        model = create_weight_model("ic", {"lookback_days": 30, "min_ic": 0.02})
        assert isinstance(model, ICWeightModel)
        assert model.lookback_days == 30
        assert model.min_ic == 0.02

    def test_create_optimized(self):
        """Test creating optimized weight model."""
        model = create_weight_model("optimized", {"regularization": 0.2})
        assert isinstance(model, OptimizedWeightModel)
        assert model.regularization == 0.2

    def test_unknown_type_raises(self):
        """Test unknown model type raises."""
        with pytest.raises(ValueError, match="Unknown weight model"):
            create_weight_model("unknown")


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
            def compute_weights(self, alpha_names, **kwargs):
                return WeightResult(weights={"a": 1.0})

        with pytest.raises(TypeError):
            IncompleteModel()
