from dataclasses import dataclass
import datetime
from abc import abstractmethod, ABC


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
