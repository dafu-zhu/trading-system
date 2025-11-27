import pytest
from trader.portfolio import Position, PortfolioGroup, Portfolio


class TestPosition:
    """Test cases for Position class"""

    def test_position_creation(self):
        """Test creating a position"""
        pos = Position("AAPL", 100, 150.0)
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100
        assert pos.price == 150.0

    def test_get_value(self):
        """Test position value calculation"""
        pos = Position("AAPL", 100, 150.0)
        assert pos.get_value() == 15000.0

    def test_get_value_negative_quantity(self):
        """Test position value with negative quantity (short position)"""
        pos = Position("AAPL", -50, 150.0)
        assert pos.get_value() == -7500.0

    def test_get_value_zero_quantity(self):
        """Test position value with zero quantity"""
        pos = Position("AAPL", 0, 150.0)
        assert pos.get_value() == 0.0

    def test_get_positions(self):
        """Test getting position as dictionary in list"""
        pos = Position("AAPL", 100, 150.0)
        positions = pos.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "AAPL"
        assert positions[0]["quantity"] == 100
        assert positions[0]["price"] == 150.0

    def test_position_repr(self):
        """Test position string representation"""
        pos = Position("AAPL", 100, 150.0)
        assert repr(pos) == "Position(AAPL, qty=100, price=150.0)"


class TestPortfolioGroup:
    """Test cases for PortfolioGroup class"""

    def test_group_creation(self):
        """Test creating a portfolio group"""
        group = PortfolioGroup("Tech Stocks")
        assert group.name == "Tech Stocks"
        assert len(group.components) == 0

    def test_add_position(self):
        """Test adding a position to a group"""
        group = PortfolioGroup("Tech Stocks")
        pos = Position("AAPL", 100, 150.0)
        group.add(pos)
        assert len(group.components) == 1

    def test_remove_position(self):
        """Test removing a position from a group"""
        group = PortfolioGroup("Tech Stocks")
        pos = Position("AAPL", 100, 150.0)
        group.add(pos)
        group.remove(pos)
        assert len(group.components) == 0

    def test_get_value_single_position(self):
        """Test group value with single position"""
        group = PortfolioGroup("Tech Stocks")
        pos = Position("AAPL", 100, 150.0)
        group.add(pos)
        assert group.get_value() == 15000.0

    def test_get_value_multiple_positions(self):
        """Test group value with multiple positions"""
        group = PortfolioGroup("Tech Stocks")
        group.add(Position("AAPL", 100, 150.0))
        group.add(Position("GOOGL", 50, 200.0))
        assert group.get_value() == 25000.0

    def test_get_value_empty_group(self):
        """Test group value when empty"""
        group = PortfolioGroup("Tech Stocks")
        assert group.get_value() == 0.0

    def test_get_value_nested_groups(self):
        """Test group value with nested groups"""
        parent = PortfolioGroup("All Stocks")
        tech = PortfolioGroup("Tech")
        finance = PortfolioGroup("Finance")

        tech.add(Position("AAPL", 100, 150.0))
        tech.add(Position("GOOGL", 50, 200.0))
        finance.add(Position("JPM", 75, 100.0))

        parent.add(tech)
        parent.add(finance)

        assert parent.get_value() == 32500.0

    def test_get_positions_single(self):
        """Test getting positions from group with single position"""
        group = PortfolioGroup("Tech Stocks")
        group.add(Position("AAPL", 100, 150.0))
        positions = group.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "AAPL"

    def test_get_positions_multiple(self):
        """Test getting positions from group with multiple positions"""
        group = PortfolioGroup("Tech Stocks")
        group.add(Position("AAPL", 100, 150.0))
        group.add(Position("GOOGL", 50, 200.0))
        positions = group.get_positions()
        assert len(positions) == 2

    def test_get_positions_nested(self):
        """Test getting positions from nested groups"""
        parent = PortfolioGroup("All Stocks")
        tech = PortfolioGroup("Tech")

        tech.add(Position("AAPL", 100, 150.0))
        tech.add(Position("GOOGL", 50, 200.0))
        parent.add(tech)

        positions = parent.get_positions()
        assert len(positions) == 2

    def test_group_repr(self):
        """Test group string representation"""
        group = PortfolioGroup("Tech Stocks")
        group.add(Position("AAPL", 100, 150.0))
        assert repr(group) == "PortfolioGroup(Tech Stocks, components=1)"


class TestPortfolio:
    """Test cases for Portfolio class"""

    def test_portfolio_creation(self):
        """Test creating a portfolio"""
        portfolio = Portfolio()
        assert portfolio.root is not None
        assert portfolio.root.name == "root"
        assert len(portfolio._position_index) == 0

    def test_add_position_to_root(self):
        """Test adding position to root group"""
        portfolio = Portfolio()
        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, portfolio.root)

        assert len(portfolio._position_index) == 1
        assert "AAPL" in portfolio._position_index
        assert portfolio._position_index["AAPL"] == pos

    def test_add_position_to_subgroup(self):
        """Test adding position to a subgroup"""
        portfolio = Portfolio()
        tech_group = PortfolioGroup("Tech")
        portfolio.root.add(tech_group)

        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, tech_group)

        assert len(portfolio._position_index) == 1
        assert "AAPL" in portfolio._position_index

    def test_update_quantity_existing_symbol(self):
        """Test updating quantity for existing symbol"""
        portfolio = Portfolio()
        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, portfolio.root)

        portfolio.update_quantity("AAPL", 50)
        assert pos.quantity == 150

        portfolio.update_quantity("AAPL", -25)
        assert pos.quantity == 125

    def test_update_quantity_nonexistent_symbol(self):
        """Test updating quantity for non-existent symbol raises ValueError"""
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="Symbol AAPL not found"):
            portfolio.update_quantity("AAPL", 50)

    def test_update_price_existing_symbol(self):
        """Test updating price for existing symbol"""
        portfolio = Portfolio()
        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, portfolio.root)

        portfolio.update_price("AAPL", 155.0)
        assert pos.price == 155.0

    def test_update_price_nonexistent_symbol(self):
        """Test updating price for non-existent symbol raises ValueError"""
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="Symbol AAPL not found"):
            portfolio.update_price("AAPL", 155.0)

    def test_get_total_value_single_position(self):
        """Test total portfolio value with single position"""
        portfolio = Portfolio()
        portfolio.add_position(Position("AAPL", 100, 150.0), portfolio.root)
        assert portfolio.get_total_value() == 15000.0

    def test_get_total_value_multiple_positions(self):
        """Test total portfolio value with multiple positions"""
        portfolio = Portfolio()
        portfolio.add_position(Position("AAPL", 100, 150.0), portfolio.root)
        portfolio.add_position(Position("GOOGL", 50, 200.0), portfolio.root)
        assert portfolio.get_total_value() == 25000.0

    def test_get_total_value_nested_groups(self):
        """Test total portfolio value with nested groups"""
        portfolio = Portfolio()
        tech = PortfolioGroup("Tech")
        finance = PortfolioGroup("Finance")

        portfolio.root.add(tech)
        portfolio.root.add(finance)

        portfolio.add_position(Position("AAPL", 100, 150.0), tech)
        portfolio.add_position(Position("JPM", 75, 100.0), finance)

        assert portfolio.get_total_value() == 22500.0

    def test_get_total_value_empty_portfolio(self):
        """Test total value of empty portfolio"""
        portfolio = Portfolio()
        assert portfolio.get_total_value() == 0.0

    def test_get_position_existing_symbol(self):
        """Test getting position for existing symbol"""
        portfolio = Portfolio()
        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, portfolio.root)

        result = portfolio.get_position("AAPL")
        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["quantity"] == 100
        assert result[0]["price"] == 150.0

    def test_get_position_nonexistent_symbol(self):
        """Test getting position for non-existent symbol raises ValueError"""
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="Symbol NONEXISTENT not found"):
            portfolio.get_position("NONEXISTENT")

    def test_get_positions_all(self):
        """Test getting all positions"""
        portfolio = Portfolio()
        portfolio.add_position(Position("AAPL", 100, 150.0), portfolio.root)
        portfolio.add_position(Position("GOOGL", 50, 200.0), portfolio.root)

        positions = portfolio.get_positions()
        assert len(positions) == 2
        symbols = [p["symbol"] for p in positions]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols

    def test_get_positions_empty(self):
        """Test getting positions from empty portfolio"""
        portfolio = Portfolio()
        positions = portfolio.get_positions()
        assert len(positions) == 0

    def test_duplicate_symbol_different_groups(self):
        """Test adding same symbol to different groups - LOGIC ERROR"""
        portfolio = Portfolio()
        tech = PortfolioGroup("Tech")
        portfolio.root.add(tech)

        pos1 = Position("AAPL", 100, 150.0)
        pos2 = Position("AAPL", 50, 155.0)

        portfolio.add_position(pos1, portfolio.root)
        with pytest.raises(ValueError, match=f"Symbol {pos2.symbol} already exists in portfolio"):
            portfolio.add_position(pos2, tech)

    def test_value_after_quantity_update(self):
        """Test that value changes correctly after quantity update"""
        portfolio = Portfolio()
        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, portfolio.root)

        initial_value = portfolio.get_total_value()
        assert initial_value == 15000.0

        portfolio.update_quantity("AAPL", 50)
        new_value = portfolio.get_total_value()
        assert new_value == 22500.0

    def test_value_after_price_update(self):
        """Test that value changes correctly after price update"""
        portfolio = Portfolio()
        pos = Position("AAPL", 100, 150.0)
        portfolio.add_position(pos, portfolio.root)

        initial_value = portfolio.get_total_value()
        assert initial_value == 15000.0

        portfolio.update_price("AAPL", 160.0)
        new_value = portfolio.get_total_value()
        assert new_value == 16000.0


# Additional pytest-style fixtures and parametrized tests
class TestPositionParametrized:
    """Parametrized tests for Position class"""

    @pytest.mark.parametrize("symbol,quantity,price,expected_value", [
        ("AAPL", 100, 150.0, 15000.0),
        ("GOOGL", 50, 200.0, 10000.0),
        ("MSFT", 75, 300.0, 22500.0),
        ("TSLA", -20, 250.0, -5000.0),  # Short position
        ("AMZN", 0, 100.0, 0.0),  # Zero quantity
    ])
    def test_position_value_parametrized(self, symbol, quantity, price, expected_value):
        """Test position value calculation with various inputs"""
        pos = Position(symbol, quantity, price)
        assert pos.get_value() == expected_value


@pytest.fixture
def empty_portfolio():
    """Fixture that provides an empty portfolio"""
    return Portfolio()


@pytest.fixture
def portfolio_with_positions():
    """Fixture that provides a portfolio with sample positions"""
    portfolio = Portfolio()
    portfolio.add_position(Position("AAPL", 100, 150.0), portfolio.root)
    portfolio.add_position(Position("GOOGL", 50, 200.0), portfolio.root)
    portfolio.add_position(Position("MSFT", 75, 300.0), portfolio.root)
    return portfolio


class TestPortfolioWithFixtures:
    """Test Portfolio using pytest fixtures"""

    def test_empty_portfolio_value(self, empty_portfolio):
        """Test that empty portfolio has zero value"""
        assert empty_portfolio.get_total_value() == 0.0

    def test_portfolio_total_value(self, portfolio_with_positions):
        """Test total value calculation with fixtures"""
        # 100*150 + 50*200 + 75*300 = 15000 + 10000 + 22500 = 47500
        assert portfolio_with_positions.get_total_value() == 47500.0

    def test_portfolio_has_three_positions(self, portfolio_with_positions):
        """Test that fixture portfolio has three positions"""
        positions = portfolio_with_positions.get_positions()
        assert len(positions) == 3
