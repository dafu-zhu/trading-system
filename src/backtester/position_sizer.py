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

logger = logging.getLogger("src.backtester.position_sizer")


class PositionSizer:
    """
    Calculate position size based on portfolio state and risk parameters.

    Supported sizing methods:
    - 'fixed': Fixed number of shares
    - 'percent_equity': Fixed percentage of portfolio value
    - 'risk_based': Based on risk per trade and stop loss distance
    - 'volatility_adjusted': Adjust size based on price volatility
    """

    def __init__(
        self,
        sizing_method: str = 'fixed',
        fixed_quantity: int = 100,
        equity_percent: float = 0.10,
        risk_per_trade: float = 0.02,
        target_volatility: float = 0.02,
        min_quantity: int = 1,
        max_quantity: Optional[int] = None
    ):
        """
        Initialize position sizer.

        :param sizing_method: Method to use ('fixed', 'percent_equity', 'risk_based', 'volatility_adjusted')
        :param fixed_quantity: Number of shares for 'fixed' method
        :param equity_percent: Percentage of equity per position (0.10 = 10%)
        :param risk_per_trade: Maximum portfolio % to risk per trade (0.02 = 2%)
        :param target_volatility: Target volatility for volatility-adjusted sizing
        :param min_quantity: Minimum shares to trade
        :param max_quantity: Maximum shares to trade (None = no limit)
        """
        valid_methods = ['fixed', 'percent_equity', 'risk_based', 'volatility_adjusted']
        if sizing_method not in valid_methods:
            raise ValueError(f"Invalid sizing_method. Must be one of {valid_methods}")

        self.sizing_method = sizing_method
        self.fixed_quantity = fixed_quantity
        self.equity_percent = equity_percent
        self.risk_per_trade = risk_per_trade
        self.target_volatility = target_volatility
        self.min_quantity = min_quantity
        self.max_quantity = max_quantity

    def calculate_qty(
        self,
        signal: Dict,
        portfolio: Portfolio,
        price: float
    ) -> int:
        """
        Calculate position size based on configured method.

        :param signal: Trading signal dictionary (may contain 'stop_loss', 'volatility', etc.)
        :param portfolio: Current portfolio state
        :param price: Current price of the instrument
        :return: Number of shares to trade
        """
        if self.sizing_method == 'fixed':
            qty = self._fixed_sizing()

        elif self.sizing_method == 'percent_equity':
            qty = self._percent_equity_sizing(portfolio, price)

        elif self.sizing_method == 'risk_based':
            qty = self._risk_based_sizing(signal, portfolio, price)

        elif self.sizing_method == 'volatility_adjusted':
            qty = self._volatility_adjusted_sizing(signal, portfolio, price)

        else:
            logger.warning(f"Unknown sizing method {self.sizing_method}, using fixed")
            qty = self._fixed_sizing()

        # Apply constraints
        qty = max(self.min_quantity, qty)
        if self.max_quantity is not None:
            qty = min(self.max_quantity, qty)

        return int(qty)

    def _fixed_sizing(self) -> int:
        """Return fixed quantity."""
        return self.fixed_quantity

    def _percent_equity_sizing(self, portfolio: Portfolio, price: float) -> int:
        """
        Size position as a percentage of total equity.

        Example: If equity is $100,000 and equity_percent is 0.10,
                 allocate $10,000 to this position.
        """
        equity = portfolio.get_total_value()
        position_value = equity * self.equity_percent

        if price <= 0:
            logger.warning(f"Invalid price {price}, using fixed sizing")
            return self.fixed_quantity

        qty = position_value / price
        logger.debug(f"Percent equity sizing: equity=${equity:.2f}, "
                    f"allocation={self.equity_percent:.1%}, qty={qty:.0f}")
        return int(qty)

    def _risk_based_sizing(
        self,
        signal: Dict,
        portfolio: Portfolio,
        price: float
    ) -> int:
        """
        Size position based on risk per trade and stop loss distance.

        Formula: qty = (portfolio_value * risk_per_trade) / stop_loss_distance

        Example: Portfolio = $100,000, risk = 2%, price = $100, stop = $98
                 Risk amount = $2,000
                 Stop distance = $2
                 Quantity = $2,000 / $2 = 1,000 shares

        Note: Signal should contain 'stop_loss' price or 'stop_loss_pct' percentage.
        """
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
            return self.fixed_quantity

        qty = risk_amount / stop_distance
        logger.debug(f"Risk-based sizing: risk_amount=${risk_amount:.2f}, "
                    f"stop_distance=${stop_distance:.2f}, qty={qty:.0f}")
        return int(qty)

    def _volatility_adjusted_sizing(
        self,
        signal: Dict,
        portfolio: Portfolio,
        price: float
    ) -> int:
        """
        Adjust position size based on volatility (inverse volatility sizing).

        Higher volatility → smaller position
        Lower volatility → larger position

        Formula: base_qty * (target_volatility / actual_volatility)

        Note: Signal should contain 'volatility' (e.g., 20-day ATR or std dev).
        """
        # Get volatility from signal
        volatility = signal.get('volatility', None)

        if volatility is None or volatility <= 0:
            logger.warning(f"Invalid volatility {volatility}, using percent equity sizing")
            return self._percent_equity_sizing(portfolio, price)

        # Calculate base quantity using percent of equity
        base_qty = self._percent_equity_sizing(portfolio, price)

        # Adjust by volatility ratio
        vol_ratio = self.target_volatility / volatility
        adjusted_qty = base_qty * vol_ratio

        logger.debug(f"Volatility-adjusted sizing: base_qty={base_qty}, "
                    f"volatility={volatility:.4f}, ratio={vol_ratio:.2f}, "
                    f"adjusted_qty={adjusted_qty:.0f}")
        return int(adjusted_qty)


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
    sizer = PositionSizer(sizing_method='fixed', fixed_quantity=100)
    qty = sizer.calculate_qty(signal, portfolio, price)
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")

    # Example 2: Percent of equity
    print("\n[Example 2] Percent of Equity (10%)")
    sizer = PositionSizer(sizing_method='percent_equity', equity_percent=0.10)
    qty = sizer.calculate_qty(signal, portfolio, price)
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")
    print(f"  Percent of Portfolio: {(qty * price) / portfolio.get_total_value():.1%}")

    # Example 3: Risk-based
    print("\n[Example 3] Risk-Based (2% risk per trade)")
    sizer = PositionSizer(sizing_method='risk_based', risk_per_trade=0.02)
    qty = sizer.calculate_qty(signal, portfolio, price)
    stop_distance = abs(price - signal['stop_loss'])
    max_loss = qty * stop_distance
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")
    print(f"  Stop Distance: ${stop_distance:.2f}")
    print(f"  Max Loss if stopped: ${max_loss:,.2f} ({max_loss/portfolio.get_total_value():.2%})")

    # Example 4: Volatility adjusted
    print("\n[Example 4] Volatility-Adjusted (target 2% vol)")
    sizer = PositionSizer(
        sizing_method='volatility_adjusted',
        equity_percent=0.10,
        target_volatility=0.02
    )
    qty = sizer.calculate_qty(signal, portfolio, price)
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")
    print(f"  Adjustment: Higher vol → smaller position")

    # Example 5: With constraints
    print("\n[Example 5] With Min/Max Constraints")
    sizer = PositionSizer(
        sizing_method='percent_equity',
        equity_percent=0.50,  # Try to use 50%
        min_quantity=10,
        max_quantity=500
    )
    qty = sizer.calculate_qty(signal, portfolio, price)
    print(f"  Desired: {(portfolio.get_total_value() * 0.50 / price):.0f} shares (50% equity)")
    print(f"  Actual: {qty} shares (capped at max_quantity=500)")
    print(f"  Position Value: ${qty * price:,.2f}")

    print("\n" + "=" * 70)
