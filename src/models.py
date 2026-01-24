from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from abc import abstractmethod, ABC
from typing import Optional, Iterator, Sequence, Callable, TYPE_CHECKING
from enum import Enum

from config.trading_config import DataType, AssetType

if TYPE_CHECKING:
    from config.trading_config import SymbolConfig
    from portfolio import Portfolio
    from orders.order import Order


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"

    @property
    def multiplier(self) -> int:
        """Numeric multiplier for calculations: BUY=1, SELL=-1."""
        return 1 if self == OrderSide.BUY else -1


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(Enum):
    """Time in force enumeration."""
    DAY = "day"
    GTC = "gtc"  # Good til canceled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class Timeframe(Enum):
    """Bar timeframe enumeration."""
    MIN_1 = "1Min"
    MIN_5 = "5Min"
    MIN_15 = "15Min"
    MIN_30 = "30Min"
    HOUR_1 = "1Hour"
    HOUR_4 = "4Hour"
    DAY_1 = "1Day"
    WEEK_1 = "1Week"
    MONTH_1 = "1Month"


@dataclass
class Bar:
    """OHLCV bar data."""
    symbol: str
    timestamp: datetime.datetime
    timeframe: Timeframe
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    trade_count: Optional[int] = None


@dataclass
class MarketCalendarDay:
    """Market calendar entry for a trading day."""
    date: datetime.date
    open_time: datetime.datetime
    close_time: datetime.datetime
    is_open: bool = True
    early_close: bool = False


@dataclass
class AccountInfo:
    """Trading account information."""
    account_id: str
    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    currency: str = "USD"
    is_paper: bool = True


@dataclass
class PositionInfo:
    """Position information from broker."""
    symbol: str
    quantity: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float
    side: str  # "long" or "short"


@dataclass
class OrderResult:
    """Result of an order submission."""
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    filled_quantity: float
    status: str  # "new", "filled", "partially_filled", "canceled", "rejected"
    submitted_at: Optional[datetime.datetime] = None
    filled_at: Optional[datetime.datetime] = None
    filled_avg_price: Optional[float] = None
    message: Optional[str] = None


@dataclass
class MarketDataPoint:
    """Real-time market data point from streaming feed."""

    timestamp: datetime.datetime
    symbol: str
    price: float
    volume: float = 0.0
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None


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


class Gateway(ABC):
    """
    Abstract base class for market data gateways.

    A gateway is responsible for providing market data to the trading system,
    either from live sources or historical data files.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the data source.
        :return bool: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the data source."""
        pass

    @abstractmethod
    def stream_data(self) -> Iterator[MarketDataPoint]:
        """
        Stream market data points.
        :return yield MarketDataPoint: Individual market data ticks
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if gateway is connected.
        :return bool: True if connected, False otherwise
        """
        pass

    @abstractmethod
    def get_current_tick(self) -> Optional[MarketDataPoint]:
        """
        Get the current market data point without advancing.
        :return Optional[MarketDataPoint]: Current tick or None if not available
        """
        pass


class DataGateway(ABC):
    """
    Abstract base class for market data gateways.

    A data gateway provides historical and real-time market data from
    external sources like Alpaca, with optional local caching.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the data source.
        :return: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the data source."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if gateway is connected.
        :return: True if connected, False otherwise
        """
        pass

    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> list[Bar]:
        """
        Fetch historical bars for a symbol.
        :param symbol: Stock symbol
        :param timeframe: Bar timeframe (1Min, 1Day, etc.)
        :param start: Start datetime (inclusive)
        :param end: End datetime (exclusive)
        :return: List of Bar objects
        """
        pass

    @abstractmethod
    def stream_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> Iterator[Bar]:
        """
        Stream bars one at a time for backtesting.
        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :return: Iterator yielding Bar objects
        """
        pass

    @abstractmethod
    def stream_realtime(
        self,
        symbols: list[str] | list[SymbolConfig],
        callback: Callable[[MarketDataPoint], None],
        data_type: DataType = DataType.TRADES,
        default_asset_type: AssetType = AssetType.STOCK,
    ) -> None:
        """
        Stream real-time market data (blocking).

        Args:
            symbols: List of symbols or SymbolConfig objects
            callback: Function called with each MarketDataPoint
            data_type: Type of data to stream (TRADES or QUOTES)
        """
        pass

    @abstractmethod
    def stop_streaming(self) -> None:
        """Stop streaming market data."""
        pass

    @abstractmethod
    def get_market_calendar(
        self,
        start: datetime.date,
        end: datetime.date,
    ) -> list[MarketCalendarDay]:
        """
        Get market calendar for a date range.
        :param start: Start date
        :param end: End date
        :return: List of MarketCalendarDay objects
        """
        pass

    @abstractmethod
    def replay_historical(
        self,
        symbols: Sequence[str | SymbolConfig],
        callback: Callable[[MarketDataPoint], None],
        timeframe: Timeframe,
        start: datetime.datetime,
        end: datetime.datetime,
        speed: float = 1.0,
    ) -> None:
        """
        Replay historical data as simulated real-time stream.

        :param symbols: List of symbols (strings or SymbolConfig) to replay
        :param callback: Function called with each MarketDataPoint
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :param speed: Replay speed multiplier (1.0 = real-time, 0 = instant)
        """
        pass


class MatchingEngine(ABC):

    @abstractmethod
    def match(self, order: Order) -> dict:
        """
        Attempt to match an order against the order book.
        :param order: The order to match
        :return: Dictionary with execution details (order_id, status,
                 filled_qty, remaining_qty, message)
        """
        pass


class PositionSizer(ABC):

    @abstractmethod
    def calculate_qty(self, signal: dict, portfolio: "Portfolio", price: float) -> float:
        """
        Calculate position size.

        :param signal: Trading signal dictionary
        :param portfolio: Current portfolio state
        :param price: Current price of the instrument
        :return: Number of shares to trade
        """
        pass


class TradingGateway(ABC):
    """
    Abstract base class for trading gateways.

    A trading gateway handles order submission, cancellation, and account/position
    queries with a broker or exchange.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the trading API.
        :return: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the trading API."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if gateway is connected.
        :return: True if connected, False otherwise
        """
        pass

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit an order to the broker.
        :param symbol: Stock symbol
        :param side: Buy or sell
        :param quantity: Number of shares
        :param order_type: Market, limit, stop, or stop-limit
        :param limit_price: Limit price (required for limit/stop-limit orders)
        :param stop_price: Stop price (required for stop/stop-limit orders)
        :param time_in_force: Order duration
        :param client_order_id: Optional client-specified order ID
        :return: OrderResult with submission details
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        :param order_id: The order ID to cancel
        :return: True if cancellation request successful, False otherwise
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderResult]:
        """
        Get the current status of an order.
        :param order_id: The order ID to query
        :return: OrderResult or None if not found
        """
        pass

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """
        Get current account information.
        :return: AccountInfo with cash, equity, buying power, etc.
        """
        pass

    @abstractmethod
    def get_positions(self) -> list[PositionInfo]:
        """
        Get all current positions.
        :return: List of PositionInfo objects
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """
        Get position for a specific symbol.
        :param symbol: Stock symbol
        :return: PositionInfo or None if no position
        """
        pass