"""
Event recorder for backtesting.

Records all events during backtest execution including:
- Order events (placed, filled, rejected)
- Position updates
- Equity curve tracking
- Trade history
"""
import pandas as pd
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass, asdict, field
from orders.order import Order, OrderSide, OrderState


@dataclass
class OrderEvent:
    """Record of an order event."""
    timestamp: datetime
    order_id: int
    symbol: str
    side: str
    quantity: float
    price: float
    event_type: str  # 'NEW', 'FILLED', 'REJECTED', 'PARTIALLY_FILLED', 'CANCELED'
    filled_qty: float = 0.0
    remaining_qty: float = 0.0
    message: str = ""


@dataclass
class PositionEvent:
    """Record of a position update."""
    timestamp: datetime
    symbol: str
    quantity: float
    price: float
    value: float
    action: str  # 'OPEN', 'INCREASE', 'DECREASE', 'CLOSE'


@dataclass
class EquitySnapshot:
    """Snapshot of portfolio equity at a point in time."""
    timestamp: datetime
    total_value: float
    cash: float
    positions_value: float
    positions: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class Trade:
    """Record of a completed trade (entry to exit)."""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    side: str  # 'BUY' or 'SELL'
    pnl: float
    return_pct: float
    duration: pd.Timedelta


class BacktestRecorder:
    """
    Record all events during backtest execution.

    Tracks orders, positions, equity curve, and completed trades.
    """

    def __init__(self):
        """Initialize the recorder."""
        self.order_events: List[OrderEvent] = []
        self.position_events: List[PositionEvent] = []
        self.equity_snapshots: List[EquitySnapshot] = []
        self.trades: List[Trade] = []

        # Track open positions for trade matching
        self._open_positions: Dict[str, Dict] = {}

    def record_order(
        self,
        timestamp: datetime,
        order: Order,
        event_type: str,
        message: str = ""
    ) -> None:
        """
        Record an order event.

        Args:
            timestamp: Time of event
            order: The order object
            event_type: Type of event (NEW, FILLED, REJECTED, etc.)
            message: Optional message/reason
        """
        event = OrderEvent(
            timestamp=timestamp,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.name,
            quantity=order.qty,
            price=order.price,
            event_type=event_type,
            filled_qty=order.filled_qty,
            remaining_qty=order.remaining_qty,
            message=message
        )
        self.order_events.append(event)

    def record_position_update(
        self,
        timestamp: datetime,
        symbol: str,
        quantity: float,
        price: float,
        action: str
    ) -> None:
        """
        Record a position update.

        Args:
            timestamp: Time of update
            symbol: Symbol being traded
            quantity: New quantity (absolute value)
            price: Price of update
            action: Type of action (OPEN, INCREASE, DECREASE, CLOSE)
        """
        value = quantity * price
        event = PositionEvent(
            timestamp=timestamp,
            symbol=symbol,
            quantity=quantity,
            price=price,
            value=value,
            action=action
        )
        self.position_events.append(event)

        # Track for trade matching
        if action == 'OPEN':
            self._open_positions[symbol] = {
                'entry_time': timestamp,
                'entry_price': price,
                'quantity': quantity
            }
        elif action == 'CLOSE' and symbol in self._open_positions:
            # Record completed trade
            self._record_trade(timestamp, symbol, quantity, price)

    def record_equity_snapshot(
        self,
        timestamp: datetime,
        total_value: float,
        cash: float,
        positions: Dict[str, Dict]
    ) -> None:
        """
        Record a snapshot of portfolio equity.

        Args:
            timestamp: Time of snapshot
            total_value: Total portfolio value
            cash: Cash position
            positions: Dictionary of positions {symbol: {quantity, price, value}}
        """
        positions_value = sum(p.get('value', 0) for p in positions.values())

        snapshot = EquitySnapshot(
            timestamp=timestamp,
            total_value=total_value,
            cash=cash,
            positions_value=positions_value,
            positions=positions.copy()
        )
        self.equity_snapshots.append(snapshot)

    def _record_trade(
        self,
        exit_time: datetime,
        symbol: str,
        quantity: float,
        exit_price: float
    ) -> None:
        """
        Record a completed trade.

        Args:
            exit_time: Time of exit
            symbol: Symbol traded
            quantity: Quantity traded
            exit_price: Exit price
        """
        if symbol not in self._open_positions:
            return

        entry_info = self._open_positions[symbol]
        entry_time = entry_info['entry_time']
        entry_price = entry_info['entry_price']

        # Calculate PnL (assuming BUY side for simplicity)
        pnl = (exit_price - entry_price) * quantity
        return_pct = (exit_price / entry_price) - 1
        duration = exit_time - entry_time

        trade = Trade(
            symbol=symbol,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            side='BUY',  # TODO: Track actual side
            pnl=pnl,
            return_pct=return_pct,
            duration=duration
        )
        self.trades.append(trade)

        # Remove from open positions
        del self._open_positions[symbol]

    def get_equity_curve(self) -> pd.Series:
        """
        Get equity curve as a pandas Series.

        Returns:
            Time series of portfolio value
        """
        if not self.equity_snapshots:
            return pd.Series()

        timestamps = [s.timestamp for s in self.equity_snapshots]
        values = [s.total_value for s in self.equity_snapshots]

        return pd.Series(values, index=pd.DatetimeIndex(timestamps))

    def get_returns(self) -> pd.Series:
        """
        Get returns series calculated from equity curve.

        Returns:
            Time series of period returns
        """
        equity = self.get_equity_curve()
        if len(equity) < 2:
            return pd.Series()
        return equity.pct_change().dropna()

    def get_orders_df(self) -> pd.DataFrame:
        """
        Get order events as a DataFrame.

        Returns:
            DataFrame of all order events
        """
        if not self.order_events:
            return pd.DataFrame()

        return pd.DataFrame([asdict(e) for e in self.order_events])

    def get_positions_df(self) -> pd.DataFrame:
        """
        Get position events as a DataFrame.

        Returns:
            DataFrame of all position events
        """
        if not self.position_events:
            return pd.DataFrame()

        return pd.DataFrame([asdict(e) for e in self.position_events])

    def get_trades_df(self) -> pd.DataFrame:
        """
        Get completed trades as a DataFrame.

        Returns:
            DataFrame of all completed trades
        """
        if not self.trades:
            return pd.DataFrame()

        trades_dict = [asdict(t) for t in self.trades]
        df = pd.DataFrame(trades_dict)

        # Convert duration to seconds for easier analysis
        if 'duration' in df.columns:
            df['duration_seconds'] = df['duration'].dt.total_seconds()
            df['duration_days'] = df['duration_seconds'] / 86400

        return df

    def get_trades_list(self) -> List[Dict]:
        """
        Get completed trades as list of dictionaries.

        Returns:
            List of trade dictionaries
        """
        return [asdict(t) for t in self.trades]

    def export_to_csv(self, directory: str) -> None:
        """
        Export all recorded data to CSV files.

        Args:
            directory: Directory to save CSV files
        """
        import os
        os.makedirs(directory, exist_ok=True)

        # Export orders
        orders_df = self.get_orders_df()
        if not orders_df.empty:
            orders_df.to_csv(f"{directory}/orders.csv", index=False)

        # Export positions
        positions_df = self.get_positions_df()
        if not positions_df.empty:
            positions_df.to_csv(f"{directory}/positions.csv", index=False)

        # Export trades
        trades_df = self.get_trades_df()
        if not trades_df.empty:
            trades_df.to_csv(f"{directory}/trades.csv", index=False)

        # Export equity curve
        equity = self.get_equity_curve()
        if not equity.empty:
            equity.to_csv(f"{directory}/equity_curve.csv", header=['value'])

    def get_summary(self) -> Dict:
        """
        Get summary statistics of recorded data.

        Returns:
            Dictionary of summary statistics
        """
        return {
            'total_order_events': len(self.order_events),
            'total_position_events': len(self.position_events),
            'total_equity_snapshots': len(self.equity_snapshots),
            'total_trades': len(self.trades),
            'symbols_traded': len(set(t.symbol for t in self.trades)),
            'recording_start': self.equity_snapshots[0].timestamp if self.equity_snapshots else None,
            'recording_end': self.equity_snapshots[-1].timestamp if self.equity_snapshots else None,
        }

    def clear(self) -> None:
        """Clear all recorded data."""
        self.order_events.clear()
        self.position_events.clear()
        self.equity_snapshots.clear()
        self.trades.clear()
        self._open_positions.clear()


if __name__ == '__main__':
    from datetime import timedelta

    print("=" * 70)
    print("Backtest Recorder Example")
    print("=" * 70)

    # Create recorder
    recorder = BacktestRecorder()

    # Simulate some events
    base_time = datetime(2023, 1, 1, 9, 30)

    # Record initial equity
    recorder.record_equity_snapshot(
        timestamp=base_time,
        total_value=100000,
        cash=100000,
        positions={}
    )

    # Create a sample order
    from orders.order import Order, OrderSide
    order = Order(symbol='AAPL', qty=100, price=150.0, side=OrderSide.BUY, order_id=1)

    # Record order events
    recorder.record_order(base_time, order, 'NEW')

    order.transition(OrderState.ACKED)
    recorder.record_order(base_time + timedelta(seconds=1), order, 'ACKED')

    order.fill(100)
    recorder.record_order(base_time + timedelta(seconds=2), order, 'FILLED')

    # Record position update
    recorder.record_position_update(
        timestamp=base_time + timedelta(seconds=2),
        symbol='AAPL',
        quantity=100,
        price=150.0,
        action='OPEN'
    )

    # Record equity after trade
    recorder.record_equity_snapshot(
        timestamp=base_time + timedelta(minutes=1),
        total_value=100000,
        cash=85000,
        positions={'AAPL': {'quantity': 100, 'price': 150.0, 'value': 15000}}
    )

    # Simulate exit
    exit_time = base_time + timedelta(days=5)
    recorder.record_position_update(
        timestamp=exit_time,
        symbol='AAPL',
        quantity=100,
        price=155.0,
        action='CLOSE'
    )

    # Print summary
    print("\nRecorder Summary:")
    summary = recorder.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # Show trades
    print("\n" + "=" * 70)
    print("Completed Trades:")
    print("=" * 70)
    trades_df = recorder.get_trades_df()
    if not trades_df.empty:
        print(trades_df[['symbol', 'entry_price', 'exit_price', 'pnl', 'return_pct', 'duration_days']])
    else:
        print("No trades recorded")

    # Show equity curve
    print("\n" + "=" * 70)
    print("Equity Curve:")
    print("=" * 70)
    equity = recorder.get_equity_curve()
    print(equity)
