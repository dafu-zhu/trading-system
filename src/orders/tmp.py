from enum import Enum

class OrderSide(Enum):
    """Order side enumeration."""
    BUY = 1
    SELL = -1
    HOLD = 0

buy = OrderSide.BUY

print(buy)
print(buy.name)
print(buy.value)
print(buy == OrderSide.BUY)