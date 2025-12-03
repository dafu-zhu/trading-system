"""
Position sizing strategies for backtesting.

Determines how many shares/contracts to trade based on various methods:
- Fixed quantity
- Percentage of equity
- Risk-based (using stop loss)
- Volatility-based
"""
import logging
from typing import Dict, Optional
from portfolio import Portfolio
from models import PositionSizer

logger = logging.getLogger("src.backtester.position_sizer")


class FixedSizer(PositionSizer):
    """
    Position sizing based on fixed number of shares
    """
    def __init__(self, fixed_qty: float, min_qty: float=1, max_qty: Optional[float]=None):
        self.fixed_qty = fixed_qty
        self.min_qty = min_qty
        self.max_qty = max_qty

    def calculate_qty(self, signal: dict, portfolio, price: float):
        qty = self.fixed_qty
        # Apply constraints
        qty = max(self.min_qty, qty)
        if self.max_qty is not None:
            qty = min(self.max_qty, qty)
        return qty


class PercentSizer(PositionSizer):
    """
    Equity percentage sizing
    """
    def __init__(self, equity_percent: float=0.10):
        self.equity_percent = equity_percent

    def calculate_qty(self, signal: dict, portfolio, price: float):
        equity = portfolio.get_total_value()
        position_value = equity * self.equity_percent
        if price <= 0:
            logger.warning(f"Invalid price {price}")
        qty = position_value / price
        logger.debug(f"Percent equity sizing: equity=${equity:.2f}, "
                     f"allocation={self.equity_percent:.1%}, qty={qty:.0f}")

        return qty


class RiskBasedSizer(PositionSizer):
    """
    Size position based on risk per trade and stop loss distance.

    Formula: qty = (portfolio_value * risk_per_trade) / stop_loss_distance

    Example: Portfolio = $100,000, risk = 2%, price = $100, stop = $98
             Risk amount = $2,000
             Stop distance = $2
             Quantity = $2,000 / $2 = 1,000 shares

    Note: Signal should contain 'stop_loss' price or 'stop_loss_pct' percentage.
    """
    def __init__(self, risk_per_trade: float):
        self.risk_per_trade = risk_per_trade

    def calculate_qty(self, signal: dict, portfolio, price: float):
        equity = portfolio.get_total_value()
        risk_amount = equity * self.risk_per_trade

        # Get stop loss distance from signal or use default
        if 'stop_loss' in signal:
            stop_loss_price = signal['stop_loss']
            stop_distance = abs(price - stop_loss_price)
        elif 'stop_loss_pct' in signal:
            stop_distance = price * signal['stop_loss_pct']
        else:
            # Default: 2% stop loss
            stop_distance = price * 0.02
            logger.debug(f"No stop loss in signal, using default 2% stop")

        if stop_distance <= 0:
            logger.warning(f"Invalid stop distance {stop_distance}, using fixed sizing")

        qty = risk_amount / stop_distance
        logger.debug(f"Risk-based sizing: risk_amount=${risk_amount:.2f}, "
                     f"stop_distance=${stop_distance:.2f}, qty={qty:.0f}")
        return qty


if __name__ == '__main__':
    from portfolio import Portfolio, Position

    print("=" * 70)
    print("Position Sizer Examples")
    print("=" * 70)

    # Create a sample portfolio
    portfolio = Portfolio(init_capital=100_000)

    # Sample signal
    signal = {
        'action': 'BUY',
        'symbol': 'AAPL',
        'price': 150.0,
        'stop_loss': 147.0,  # $3 stop
        'volatility': 0.015  # 1.5% volatility
    }
    price = 150.0

    print(f"\nPortfolio Value: ${portfolio.get_total_value():,.2f}")
    print(f"Signal: {signal['action']} {signal['symbol']} @ ${price}")
    print(f"Stop Loss: ${signal['stop_loss']}")
    print(f"Volatility: {signal['volatility']:.2%}")
    print("\n" + "=" * 70)

    # Example 1: Fixed sizing
    print("\n[Example 1] Fixed Sizing")
    sizer = FixedSizer(fixed_qty=100)
    qty = sizer.calculate_qty(signal, portfolio, price)
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")

    # Example 2: Percent of equity
    print("\n[Example 2] Percent of Equity (10%)")
    sizer = PercentSizer(equity_percent=0.10)
    qty = sizer.calculate_qty(signal, portfolio, price)
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")
    print(f"  Percent of Portfolio: {(qty * price) / portfolio.get_total_value():.1%}")

    # Example 3: Risk-based
    print("\n[Example 3] Risk-Based (2% risk per trade)")
    sizer = RiskBasedSizer(risk_per_trade=0.02)
    qty = sizer.calculate_qty(signal, portfolio, price)
    stop_distance = abs(price - signal['stop_loss'])
    max_loss = qty * stop_distance
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")
    print(f"  Stop Distance: ${stop_distance:.2f}")
    print(f"  Max Loss if stopped: ${max_loss:,.2f} ({max_loss/portfolio.get_total_value():.2%})")
