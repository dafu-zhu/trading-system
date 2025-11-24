from dataclasses import dataclass
import datetime


@dataclass
class MarketDataPoint:
    timestamp: datetime.datetime
    symbol: str
    price: float