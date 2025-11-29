from dataclasses import dataclass, field
import datetime
from abc import abstractmethod, ABC
from typing import Optional


@dataclass
class MarketDataPoint:
    timestamp: datetime.datetime
    symbol: str
    price: float


class Instrument(ABC):
    """Abstract base class for financial instruments."""

    def __init__(self, symbol: str, price: float):
        self.symbol = symbol
        self.price = price

    @abstractmethod
    def get_type(self) -> str:
        """Return the instrument type."""
        pass

    def get_metrics(self) -> dict:
        """
        Return base metrics for this instrument. Can be extended by decorators.
        """
        return {
            "symbol": self.symbol,
            "price": self.price,
            "type": self.get_type()
        }

    def __repr__(self) -> str:
        return f"{self.get_type()}({self.symbol}, price={self.price})"


class PortfolioComponent(ABC):
    """Abstract component for Composite pattern."""

    @abstractmethod
    def get_value(self) -> float:
        """Calculate and return total value."""
        pass

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Return list of position information."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass


@dataclass
class FeatureConfig:
    """Configuration for a feature group with optional parameters."""
    name: str
    windows: Optional[list[int]] = None
    params: dict = field(default_factory=dict)


@dataclass
class ColumnMapping:
    """Mapping of standard column names to dataset-specific column names."""
    open: str = 'Open'
    high: str = 'High'
    low: str = 'Low'
    close: str = 'Adj Close'
    volume: str = 'Volume'

    @classmethod
    def from_dict(cls, mapping: dict) -> 'ColumnMapping':
        """Create ColumnMapping from a dictionary."""
        return cls(**mapping)


class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, tick: MarketDataPoint) -> list:
        pass