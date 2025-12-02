"""
Transaction cost models for backtesting.

Simulates realistic trading costs including:
- Commission (fixed, percentage, tiered)
- Slippage (fixed, percentage, volume-based)
- Bid-ask spread
- Market impact
"""
from typing import Optional, Dict
from orders.order import Order, OrderSide
from dataclasses import dataclass


@dataclass
class TransactionCost:
    """Result of transaction cost calculation."""
    commission: float
    slippage: float
    total_cost: float
    effective_price: float  # Actual execution price after costs


class CommissionModel:
    """Base class for commission models."""

    def calculate(self, order: Order, fill_price: float) -> float:
        """
        Calculate commission for an order.

        Args:
            order: The order being filled
            fill_price: Price at which order is filled

        Returns:
            Commission amount in dollars
        """
        raise NotImplementedError


class FixedCommission(CommissionModel):
    """Fixed commission per trade."""

    def __init__(self, commission_per_trade: float = 0.0):
        """
        Initialize fixed commission model.

        Args:
            commission_per_trade: Fixed commission per trade (e.g., $1.00)
        """
        self.commission_per_trade = commission_per_trade

    def calculate(self, order: Order, fill_price: float) -> float:
        """Calculate fixed commission."""
        return self.commission_per_trade


class PerShareCommission(CommissionModel):
    """Commission per share traded."""

    def __init__(self, commission_per_share: float = 0.005, min_commission: float = 1.0):
        """
        Initialize per-share commission model.

        Args:
            commission_per_share: Commission per share (e.g., $0.005)
            min_commission: Minimum commission per trade
        """
        self.commission_per_share = commission_per_share
        self.min_commission = min_commission

    def calculate(self, order: Order, fill_price: float) -> float:
        """Calculate per-share commission with minimum."""
        commission = order.filled_qty * self.commission_per_share
        return max(commission, self.min_commission)


class PercentageCommission(CommissionModel):
    """Commission as percentage of trade value."""

    def __init__(self, commission_pct: float = 0.001, min_commission: float = 1.0):
        """
        Initialize percentage commission model.

        Args:
            commission_pct: Commission as decimal (e.g., 0.001 = 0.1%)
            min_commission: Minimum commission per trade
        """
        self.commission_pct = commission_pct
        self.min_commission = min_commission

    def calculate(self, order: Order, fill_price: float) -> float:
        """Calculate percentage-based commission with minimum."""
        trade_value = order.filled_qty * fill_price
        commission = trade_value * self.commission_pct
        return max(commission, self.min_commission)


class TieredCommission(CommissionModel):
    """Tiered commission based on trade value."""

    def __init__(self, tiers: Dict[float, float], min_commission: float = 1.0):
        """
        Initialize tiered commission model.

        Args:
            tiers: Dictionary of {max_value: commission_rate}
                   Example: {10000: 0.002, 50000: 0.0015, float('inf'): 0.001}
            min_commission: Minimum commission per trade
        """
        # Sort tiers by max_value
        self.tiers = sorted(tiers.items(), key=lambda x: x[0])
        self.min_commission = min_commission

    def calculate(self, order: Order, fill_price: float) -> float:
        """Calculate tiered commission."""
        trade_value = order.filled_qty * fill_price

        # Find applicable tier
        commission_rate = 0.0
        for max_value, rate in self.tiers:
            if trade_value <= max_value:
                commission_rate = rate
                break

        commission = trade_value * commission_rate
        return max(commission, self.min_commission)


class SlippageModel:
    """Base class for slippage models."""

    def calculate(self, order: Order, market_price: float) -> float:
        """
        Calculate slippage cost.

        Args:
            order: The order being filled
            market_price: Current market price

        Returns:
            Slippage cost in dollars (always positive)
        """
        raise NotImplementedError

    def get_execution_price(self, order: Order, market_price: float) -> float:
        """
        Get actual execution price after slippage.

        Args:
            order: The order being filled
            market_price: Current market price

        Returns:
            Actual execution price
        """
        raise NotImplementedError


class FixedSlippage(SlippageModel):
    """Fixed slippage per share."""

    def __init__(self, slippage_per_share: float = 0.01):
        """
        Initialize fixed slippage model.

        Args:
            slippage_per_share: Fixed slippage per share (e.g., $0.01)
        """
        self.slippage_per_share = slippage_per_share

    def get_execution_price(self, order: Order, market_price: float) -> float:
        """Get execution price with fixed slippage."""
        if order.side == OrderSide.BUY:
            return market_price + self.slippage_per_share
        else:  # SELL
            return market_price - self.slippage_per_share

    def calculate(self, order: Order, market_price: float) -> float:
        """Calculate fixed slippage cost."""
        return order.filled_qty * self.slippage_per_share


class PercentageSlippage(SlippageModel):
    """Slippage as percentage of price."""

    def __init__(self, slippage_pct: float = 0.0005):
        """
        Initialize percentage slippage model.

        Args:
            slippage_pct: Slippage as decimal (e.g., 0.0005 = 0.05% or 5 bps)
        """
        self.slippage_pct = slippage_pct

    def get_execution_price(self, order: Order, market_price: float) -> float:
        """Get execution price with percentage slippage."""
        slippage_amount = market_price * self.slippage_pct
        if order.side == OrderSide.BUY:
            return market_price + slippage_amount
        else:  # SELL
            return market_price - slippage_amount

    def calculate(self, order: Order, market_price: float) -> float:
        """Calculate percentage slippage cost."""
        slippage_per_share = market_price * self.slippage_pct
        return order.filled_qty * slippage_per_share


class VolumeSlippage(SlippageModel):
    """Slippage based on order size relative to volume."""

    def __init__(
        self,
        base_slippage_pct: float = 0.0001,
        volume_impact_factor: float = 0.1
    ):
        """
        Initialize volume-based slippage model.

        Slippage increases with order size: base + (order_size / volume) * impact_factor

        Args:
            base_slippage_pct: Base slippage percentage
            volume_impact_factor: How much volume impacts slippage
        """
        self.base_slippage_pct = base_slippage_pct
        self.volume_impact_factor = volume_impact_factor

    def get_execution_price(
        self,
        order: Order,
        market_price: float,
        volume: Optional[float] = None
    ) -> float:
        """
        Get execution price with volume-based slippage.

        Args:
            order: The order
            market_price: Current market price
            volume: Market volume (if None, use base slippage only)
        """
        if volume is None or volume == 0:
            slippage_pct = self.base_slippage_pct
        else:
            # Calculate volume impact
            volume_ratio = order.qty / volume
            slippage_pct = self.base_slippage_pct + (volume_ratio * self.volume_impact_factor)

        slippage_amount = market_price * slippage_pct

        if order.side == OrderSide.BUY:
            return market_price + slippage_amount
        else:  # SELL
            return market_price - slippage_amount

    def calculate(self, order: Order, market_price: float, volume: Optional[float] = None) -> float:
        """Calculate volume-based slippage cost."""
        execution_price = self.get_execution_price(order, market_price, volume)
        price_diff = abs(execution_price - market_price)
        return order.filled_qty * price_diff


class TransactionCostCalculator:
    """
    Calculate total transaction costs including commission and slippage.
    """

    def __init__(
        self,
        commission_model: Optional[CommissionModel] = None,
        slippage_model: Optional[SlippageModel] = None
    ):
        """
        Initialize transaction cost calculator.

        Args:
            commission_model: Commission model to use (default: no commission)
            slippage_model: Slippage model to use (default: no slippage)
        """
        self.commission_model = commission_model or FixedCommission(0.0)
        self.slippage_model = slippage_model or FixedSlippage(0.0)

    def calculate_costs(
        self,
        order: Order,
        market_price: float,
        volume: Optional[float] = None
    ) -> TransactionCost:
        """
        Calculate all transaction costs for an order.

        Args:
            order: The order being filled
            market_price: Current market price
            volume: Market volume (optional, for volume-based slippage)

        Returns:
            TransactionCost object with breakdown
        """
        # Calculate effective execution price with slippage
        if isinstance(self.slippage_model, VolumeSlippage):
            effective_price = self.slippage_model.get_execution_price(order, market_price, volume)
        else:
            effective_price = self.slippage_model.get_execution_price(order, market_price)

        # Calculate costs
        commission = self.commission_model.calculate(order, effective_price)
        slippage = self.slippage_model.calculate(order, market_price)
        total_cost = commission + slippage

        return TransactionCost(
            commission=commission,
            slippage=slippage,
            total_cost=total_cost,
            effective_price=effective_price
        )

    def get_net_proceeds(
        self,
        order: Order,
        market_price: float,
        volume: Optional[float] = None
    ) -> float:
        """
        Calculate net proceeds after all costs.

        For BUY orders: -(quantity * price + costs)
        For SELL orders: (quantity * price - costs)

        Args:
            order: The order being filled
            market_price: Current market price
            volume: Market volume (optional)

        Returns:
            Net cash flow (negative for buys, positive for sells)
        """
        costs = self.calculate_costs(order, market_price, volume)
        trade_value = order.filled_qty * costs.effective_price

        if order.side == OrderSide.BUY:
            return -(trade_value + costs.commission)
        else:  # SELL
            return trade_value - costs.commission


if __name__ == '__main__':
    from orders.order import Order, OrderSide

    print("=" * 70)
    print("Transaction Cost Models Example")
    print("=" * 70)

    # Create sample order
    order = Order(symbol='AAPL', qty=100, price=150.0, side=OrderSide.BUY, order_id=1)
    order.filled_qty = 100  # Assume fully filled
    market_price = 150.0

    print(f"\nOrder: {order.side.name} {order.qty} shares @ ${market_price}")
    print(f"Trade Value: ${order.qty * market_price:,.2f}")

    # Example 1: Fixed commission
    print("\n" + "=" * 70)
    print("[Example 1] Fixed Commission ($1.00 per trade)")
    print("=" * 70)
    commission_model = FixedCommission(commission_per_trade=1.0)
    slippage_model = FixedSlippage(slippage_per_share=0.01)
    calculator = TransactionCostCalculator(commission_model, slippage_model)

    costs = calculator.calculate_costs(order, market_price)
    print(f"  Commission:       ${costs.commission:.2f}")
    print(f"  Slippage:         ${costs.slippage:.2f}")
    print(f"  Total Cost:       ${costs.total_cost:.2f}")
    print(f"  Effective Price:  ${costs.effective_price:.2f}")
    print(f"  Cost as % of trade: {costs.total_cost / (order.qty * market_price) * 100:.3f}%")

    # Example 2: Percentage commission
    print("\n" + "=" * 70)
    print("[Example 2] Percentage Commission (0.1%)")
    print("=" * 70)
    commission_model = PercentageCommission(commission_pct=0.001, min_commission=1.0)
    slippage_model = PercentageSlippage(slippage_pct=0.0005)  # 5 bps
    calculator = TransactionCostCalculator(commission_model, slippage_model)

    costs = calculator.calculate_costs(order, market_price)
    print(f"  Commission:       ${costs.commission:.2f}")
    print(f"  Slippage:         ${costs.slippage:.2f}")
    print(f"  Total Cost:       ${costs.total_cost:.2f}")
    print(f"  Effective Price:  ${costs.effective_price:.2f}")
    print(f"  Net Proceeds:     ${calculator.get_net_proceeds(order, market_price):,.2f}")

    # Example 3: Interactive Brokers-like (per share)
    print("\n" + "=" * 70)
    print("[Example 3] Per-Share Commission (like Interactive Brokers)")
    print("=" * 70)
    commission_model = PerShareCommission(commission_per_share=0.005, min_commission=1.0)
    slippage_model = PercentageSlippage(slippage_pct=0.0003)  # 3 bps
    calculator = TransactionCostCalculator(commission_model, slippage_model)

    costs = calculator.calculate_costs(order, market_price)
    print(f"  Commission:       ${costs.commission:.2f} (${commission_model.commission_per_share} per share)")
    print(f"  Slippage:         ${costs.slippage:.2f}")
    print(f"  Total Cost:       ${costs.total_cost:.2f}")
    print(f"  Cost per share:   ${costs.total_cost / order.qty:.4f}")

    # Example 4: Tiered commission
    print("\n" + "=" * 70)
    print("[Example 4] Tiered Commission")
    print("=" * 70)
    tiers = {
        10000: 0.002,   # 0.2% for trades up to $10k
        50000: 0.0015,  # 0.15% for trades up to $50k
        float('inf'): 0.001  # 0.1% for larger trades
    }
    commission_model = TieredCommission(tiers=tiers, min_commission=1.0)
    calculator = TransactionCostCalculator(commission_model, FixedSlippage(0.0))

    # Test different trade sizes
    for qty in [50, 200, 500]:
        test_order = Order(symbol='AAPL', qty=qty, price=150.0, side=OrderSide.BUY, order_id=1)
        test_order.filled_qty = qty
        costs = calculator.calculate_costs(test_order, market_price)
        trade_value = qty * market_price
        print(f"  Trade ${trade_value:>7,.0f}: Commission ${costs.commission:>6.2f} "
              f"({costs.commission/trade_value*100:.3f}%)")

    print("\n" + "=" * 70)
