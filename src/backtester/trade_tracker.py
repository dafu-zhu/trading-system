"""
Trade Tracker: Converts order fills into complete round-trip trades.
Matches entry and exit orders to calculate PnL and track trade lifecycle.
"""
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
from orders.order import OrderSide
import logging

logger = logging.getLogger(__name__)


class TradeTracker:
    """
    Tracks orders and creates complete round-trip trades for analysis.
    Uses FIFO (First-In-First-Out) matching for partial fills.
    """

    def __init__(self):
        # Track open positions per symbol: {symbol: [(qty, price, timestamp, order_id), ...]}
        self.open_positions: Dict[str, List[tuple]] = defaultdict(list)
        # Completed trades
        self.completed_trades: List[Dict] = []

    def process_fill(
        self,
        symbol: str,
        side: OrderSide,
        filled_qty: float,
        fill_price: float,
        timestamp: datetime,
        order_id: int
    ) -> None:
        """
        Process a filled order and match it with existing positions to create trades.

        Args:
            symbol: Symbol traded
            side: OrderSide.BUY or OrderSide.SELL
            filled_qty: Quantity filled
            fill_price: Price of fill
            timestamp: Time of fill
            order_id: Order ID
        """
        if side == OrderSide.BUY:
            # Opening a long position - add to open positions
            self.open_positions[symbol].append((filled_qty, fill_price, timestamp, order_id))
            logger.debug(f"Opened position: {symbol} {filled_qty} @ ${fill_price:.2f}")

        elif side == OrderSide.SELL:
            # Closing positions - match against open positions using FIFO
            remaining_qty = filled_qty

            while remaining_qty > 0 and self.open_positions[symbol]:
                # Get oldest position (FIFO)
                entry_qty, entry_price, entry_time, entry_order_id = self.open_positions[symbol][0]

                # Match quantity
                matched_qty = min(remaining_qty, entry_qty)

                # Create completed trade
                pnl = matched_qty * (fill_price - entry_price)
                pnl_pct = ((fill_price - entry_price) / entry_price) if entry_price > 0 else 0

                trade = {
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'exit_time': timestamp,
                    'entry_price': entry_price,
                    'exit_price': fill_price,
                    'quantity': matched_qty,
                    'side': 'LONG',  # Currently only handling long trades
                    'pnl': pnl,
                    'return': pnl_pct,
                    'entry_order_id': entry_order_id,
                    'exit_order_id': order_id,
                    'holding_period': (timestamp - entry_time).total_seconds() / 86400,  # days
                }

                self.completed_trades.append(trade)
                logger.debug(f"Closed trade: {symbol} {matched_qty} @ ${entry_price:.2f} -> ${fill_price:.2f}, PnL: ${pnl:.2f}")

                # Update remaining quantities
                remaining_qty -= matched_qty
                entry_qty -= matched_qty

                # Remove or update the position
                if entry_qty <= 0:
                    self.open_positions[symbol].pop(0)
                else:
                    # Update the position with reduced quantity
                    self.open_positions[symbol][0] = (entry_qty, entry_price, entry_time, entry_order_id)

            # If we still have remaining quantity, it means we're opening a short position
            # For now, we'll log a warning as the current system doesn't handle shorts
            if remaining_qty > 0:
                logger.warning(f"Sell order exceeded long position for {symbol}, remaining: {remaining_qty:.2f} - short selling not implemented")

    def get_trades(self) -> List[Dict]:
        """Get all completed trades."""
        return self.completed_trades

    def get_open_positions(self) -> Dict[str, List[tuple]]:
        """Get currently open positions that haven't been closed."""
        return dict(self.open_positions)

    def get_trade_count(self) -> int:
        """Get number of completed trades."""
        return len(self.completed_trades)

    def get_total_pnl(self) -> float:
        """Get total PnL from all completed trades."""
        return sum(trade['pnl'] for trade in self.completed_trades)
