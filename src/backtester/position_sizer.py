"""
Position sizing strategies for backtesting.

Determines how many shares/contracts to trade based on various methods:
- Fixed quantity
- Percentage of equity
- Risk-based (using stop loss)
- Volatility-based
"""

import logging
from typing import Optional
from portfolio import Portfolio
from models import PositionSizer

logger = logging.getLogger("src.backtester.position_sizer")


class FixedSizer(PositionSizer):
    """
    Position sizing based on fixed number of shares
    """

    def __init__(
        self, fixed_qty: float, min_qty: float = 1, max_qty: Optional[float] = None
    ):
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

    def __init__(self, equity_percent: float = 0.10):
        self.equity_percent = equity_percent

    def calculate_qty(self, signal: dict, portfolio, price: float):
        equity = portfolio.get_total_value()
        position_value = equity * self.equity_percent
        if price <= 0:
            logger.warning(f"Invalid price {price}")
        qty = position_value / price
        logger.debug(
            f"Percent equity sizing: equity=${equity:.2f}, "
            f"allocation={self.equity_percent:.1%}, qty={qty:.0f}"
        )

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
        if "stop_loss" in signal:
            stop_loss_price = signal["stop_loss"]
            stop_distance = abs(price - stop_loss_price)
        elif "stop_loss_pct" in signal:
            stop_distance = price * signal["stop_loss_pct"]
        else:
            # Default: 2% stop loss
            stop_distance = price * 0.02
            logger.debug("No stop loss in signal, using default 2% stop")

        if stop_distance <= 0:
            logger.warning(f"Invalid stop distance {stop_distance}, using fixed sizing")

        qty = risk_amount / stop_distance
        logger.debug(
            f"Risk-based sizing: risk_amount=${risk_amount:.2f}, "
            f"stop_distance=${stop_distance:.2f}, qty={qty:.0f}"
        )
        return qty


class KellySizer(PositionSizer):
    """
    Kelly Criterion position sizing.

    The Kelly criterion determines the optimal fraction of capital to bet
    based on the expected edge and odds.

    Formula: f* = (p*b - q) / b
    Where:
        f* = optimal fraction of capital to bet
        p = probability of winning (win rate)
        q = probability of losing (1 - p)
        b = average win / average loss ratio (win/loss ratio)

    In practice, "Half Kelly" (f*/2) or "Quarter Kelly" (f*/4) is often used
    to reduce volatility and drawdowns.

    Example:
        win_rate = 0.55 (55% wins)
        win_loss_ratio = 1.5 (wins are 1.5x losses on average)
        Kelly f* = (0.55 * 1.5 - 0.45) / 1.5 = 0.25 (25% of portfolio)
        Half Kelly = 12.5% of portfolio per trade

    Signal can override with 'win_rate' and 'win_loss_ratio' keys.
    """

    def __init__(
        self,
        win_rate: float = 0.50,
        win_loss_ratio: float = 1.0,
        kelly_fraction: float = 0.5,
        max_position_pct: float = 0.25,
        min_qty: float = 1.0,
    ):
        """
        Initialize Kelly sizer.

        Args:
            win_rate: Historical probability of winning (default: 50%)
            win_loss_ratio: Average win / average loss (default: 1.0)
            kelly_fraction: Fraction of Kelly to use (0.5 = Half Kelly)
            max_position_pct: Maximum position as % of portfolio (cap)
            min_qty: Minimum quantity to trade
        """
        self.win_rate = win_rate
        self.win_loss_ratio = win_loss_ratio
        self.kelly_fraction = kelly_fraction
        self.max_position_pct = max_position_pct
        self.min_qty = min_qty

    def calculate_kelly_fraction(self, win_rate: float, win_loss_ratio: float) -> float:
        """
        Calculate the Kelly fraction.

        Returns:
            Optimal fraction of capital to bet (can be negative if no edge)
        """
        if win_loss_ratio <= 0:
            return 0.0

        q = 1 - win_rate
        kelly = (win_rate * win_loss_ratio - q) / win_loss_ratio

        return kelly

    def calculate_qty(self, signal: dict, portfolio, price: float) -> float:
        equity = portfolio.get_total_value()

        # Use signal parameters if provided, else use defaults
        win_rate = signal.get("win_rate", self.win_rate)
        win_loss_ratio = signal.get("win_loss_ratio", self.win_loss_ratio)

        # Calculate raw Kelly fraction
        raw_kelly = self.calculate_kelly_fraction(win_rate, win_loss_ratio)

        # Apply fraction (e.g., Half Kelly)
        kelly = raw_kelly * self.kelly_fraction

        # Kelly can be negative if no edge - don't trade
        if kelly <= 0:
            logger.warning(
                f"Kelly <= 0 (no edge): win_rate={win_rate:.1%}, "
                f"w/l_ratio={win_loss_ratio:.2f}, kelly={raw_kelly:.2%}"
            )
            return 0.0

        # Cap at maximum position
        position_pct = min(kelly, self.max_position_pct)
        position_value = equity * position_pct

        if price <= 0:
            logger.warning(f"Invalid price {price}")
            return self.min_qty

        qty = position_value / price

        # Apply minimum
        qty = max(self.min_qty, qty)

        logger.debug(
            f"Kelly sizing: win_rate={win_rate:.1%}, w/l={win_loss_ratio:.2f}, "
            f"raw_kelly={raw_kelly:.2%}, applied={position_pct:.2%}, qty={qty:.0f}"
        )

        return qty


class VolatilitySizer(PositionSizer):
    """
    Volatility-based position sizing using ATR (Average True Range).

    Sizes positions so that a move of X * ATR results in a fixed % loss.
    This normalizes risk across assets with different volatilities.

    Formula: qty = (equity * risk_pct) / (ATR * multiplier)

    Example:
        Portfolio = $100,000
        Risk per trade = 2%
        ATR = $2.50
        Multiplier = 2 (stop at 2 * ATR)

        Risk amount = $100,000 * 0.02 = $2,000
        Stop distance = $2.50 * 2 = $5.00
        Quantity = $2,000 / $5.00 = 400 shares

    Signal should contain 'atr' (Average True Range value).
    Can override default_atr_pct if ATR not provided.
    """

    def __init__(
        self,
        risk_pct: float = 0.02,
        atr_multiplier: float = 2.0,
        default_atr_pct: float = 0.02,
        max_position_pct: float = 0.25,
        min_qty: float = 1.0,
    ):
        """
        Initialize volatility sizer.

        Args:
            risk_pct: Risk per trade as fraction (default: 2%)
            atr_multiplier: Stop distance as multiple of ATR (default: 2x)
            default_atr_pct: Default ATR as % of price if not in signal (2%)
            max_position_pct: Maximum position as % of portfolio
            min_qty: Minimum quantity to trade
        """
        self.risk_pct = risk_pct
        self.atr_multiplier = atr_multiplier
        self.default_atr_pct = default_atr_pct
        self.max_position_pct = max_position_pct
        self.min_qty = min_qty

    def calculate_qty(self, signal: dict, portfolio, price: float) -> float:
        equity = portfolio.get_total_value()

        # Get ATR from signal or calculate default
        if "atr" in signal:
            atr = signal["atr"]
        elif "volatility" in signal:
            # Some signals provide volatility as % of price
            atr = price * signal["volatility"]
        else:
            # Use default ATR as % of price
            atr = price * self.default_atr_pct
            logger.debug(
                f"No ATR in signal, using default {self.default_atr_pct:.1%} of price"
            )

        if atr <= 0:
            logger.warning(f"Invalid ATR {atr}, using default")
            atr = price * self.default_atr_pct

        # Calculate stop distance
        stop_distance = atr * self.atr_multiplier

        # Calculate risk amount and position size
        risk_amount = equity * self.risk_pct
        qty = risk_amount / stop_distance

        # Cap at maximum position
        max_qty_by_pct = (equity * self.max_position_pct) / price
        qty = min(qty, max_qty_by_pct)

        # Apply minimum
        qty = max(self.min_qty, qty)

        if price <= 0:
            logger.warning(f"Invalid price {price}")
            return self.min_qty

        logger.debug(
            f"Volatility sizing: ATR=${atr:.2f}, stop_dist=${stop_distance:.2f}, "
            f"risk=${risk_amount:.2f}, qty={qty:.0f}"
        )

        return qty


if __name__ == "__main__":
    from portfolio import Portfolio  # noqa: F401

    print("=" * 70)
    print("Position Sizer Examples")
    print("=" * 70)

    # Create a sample portfolio
    portfolio = Portfolio(init_capital=100_000)

    # Sample signal
    signal = {
        "action": "BUY",
        "symbol": "AAPL",
        "price": 150.0,
        "stop_loss": 147.0,  # $3 stop
        "volatility": 0.015,  # 1.5% volatility
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
    stop_distance = abs(price - signal["stop_loss"])
    max_loss = qty * stop_distance
    print(f"  Quantity: {qty} shares")
    print(f"  Position Value: ${qty * price:,.2f}")
    print(f"  Stop Distance: ${stop_distance:.2f}")
    print(
        f"  Max Loss if stopped: ${max_loss:,.2f} ({max_loss / portfolio.get_total_value():.2%})"
    )
