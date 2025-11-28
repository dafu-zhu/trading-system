from models import PortfolioComponent


class Position(PortfolioComponent):
    """Leaf node: single position in the portfolio tree."""

    def __init__(self, symbol: str, quantity: int, price: float):
        self.symbol = symbol
        self.quantity = quantity
        self.price = price

    def get_value(self) -> float:
        """Return position value"""
        return self.quantity * self.price

    def get_positions(self) -> list[dict]:
        """Return this position as a single-item list"""
        return [
            {
                "symbol": self.symbol,
                "quantity": self.quantity,
                "price": self.price
            }
        ]

    def __repr__(self) -> str:
        return f"Position({self.symbol}, qty={self.quantity}, price={self.price})"


class PortfolioGroup(PortfolioComponent):
    """Composite node: group of positions and/or sub-portfolios"""

    def __init__(self, name: str):
        self.name = name
        self.components: list[PortfolioComponent] = []

    def add(self, component: PortfolioComponent) -> None:
        """Add a child component"""
        self.components.append(component)

    def remove(self, component: PortfolioComponent) -> None:
        """Remove a child component"""
        self.components.remove(component)

    def get_value(self) -> float:
        """Recursively calculate total value of all components"""
        return sum(c.get_value() for c in self.components)

    def get_positions(self) -> list[dict]:
        """Recursively collect all positions from child components"""
        positions = []
        for component in self.components:
            positions.extend(component.get_positions())
        return positions

    def __repr__(self) -> str:
        return f"PortfolioGroup({self.name}, components={len(self.components)})"


class Portfolio:
    """
    Efficient interface for tree-based portfolio structure
    """
    def __init__(self):
        self.root = PortfolioGroup("root")
        self._position_index: dict[str, Position] = {}

    def add_position(self, position: Position, group: PortfolioGroup):
        if position.symbol in self._position_index:
            raise ValueError(f"Symbol {position.symbol} already exists in portfolio")
        group.add(position)     # add to tree, O(1)
        self._position_index[position.symbol] = position    # add to index

    def update_quantity(self, symbol: str, delta: int):
        """Update quantity of a given symbol"""
        if position := self._position_index.get(symbol):
            position.quantity += delta      # in-place update
        else:
            raise ValueError(f"Symbol {symbol} not found")

    def update_price(self, symbol: str, price: float):
        """Update average price of a given symbol in portfolio"""
        if position := self._position_index.get(symbol):
            position.price = price
        else:
            raise ValueError(f"Symbol {symbol} not found")

    def get_total_value(self) -> float:
        """Get total portfolio value"""
        return self.root.get_value()

    def get_position(self, symbol: str) -> list[dict]:
        """Get position for the specified symbol, return one element list"""
        symbol_pos: Position = self._position_index.get(symbol)
        if not symbol_pos:
            raise ValueError(f"Symbol {symbol} not found")
        return symbol_pos.get_positions()

    def get_positions(self) -> list[dict]:
        """Get all positions in portfolio"""
        return self.root.get_positions()

