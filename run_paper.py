#!/usr/bin/env python3
"""
Paper Trading Entry Point

Run paper trading with Alpaca API or in local simulation mode.

Usage:
    python run_paper.py                  # Connect to Alpaca paper trading
    python run_paper.py --simulate       # Run in local simulation mode
    python run_paper.py --info           # Show account info only
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gateway.alpaca_trading_gateway import AlpacaTradingGateway
from models import OrderSide, OrderType, TimeInForce, AccountInfo, PositionInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def show_account_info(gateway: AlpacaTradingGateway) -> None:
    """Display current account information."""
    account = gateway.get_account()
    print("\n" + "=" * 60)
    print("ACCOUNT INFORMATION")
    print("=" * 60)
    print(f"  Account ID:      {account.account_id}")
    print(f"  Mode:            {'PAPER' if account.is_paper else 'LIVE'}")
    print(f"  Currency:        {account.currency}")
    print(f"  Cash:            ${account.cash:,.2f}")
    print(f"  Portfolio Value: ${account.portfolio_value:,.2f}")
    print(f"  Buying Power:    ${account.buying_power:,.2f}")
    print(f"  Equity:          ${account.equity:,.2f}")
    print("=" * 60)


def show_positions(gateway: AlpacaTradingGateway) -> None:
    """Display current positions."""
    positions = gateway.get_positions()
    print("\n" + "=" * 60)
    print("CURRENT POSITIONS")
    print("=" * 60)
    if not positions:
        print("  No open positions")
    else:
        print(f"  {'Symbol':<8} {'Qty':>10} {'Avg Price':>12} {'Mkt Value':>14} {'P/L':>12}")
        print("  " + "-" * 56)
        for pos in positions:
            print(
                f"  {pos.symbol:<8} {pos.quantity:>10.2f} "
                f"${pos.avg_entry_price:>10.2f} ${pos.market_value:>12.2f} "
                f"${pos.unrealized_pl:>10.2f}"
            )
    print("=" * 60)


class LocalSimulator:
    """
    Local paper trading simulator.

    Simulates order execution without connecting to Alpaca.
    Useful for testing strategies without API calls.
    """

    def __init__(self, initial_cash: float = 100_000.0):
        self.cash = initial_cash
        self.positions: dict[str, dict] = {}
        self._order_id = 0

    def connect(self) -> bool:
        logger.info("Connected to LOCAL simulator (no API calls)")
        return True

    def disconnect(self) -> None:
        logger.info("Disconnected from LOCAL simulator")

    def is_connected(self) -> bool:
        return True

    def get_account(self) -> AccountInfo:
        portfolio_value = sum(
            p["quantity"] * p["current_price"] for p in self.positions.values()
        )
        return AccountInfo(
            account_id="LOCAL_SIM",
            cash=self.cash,
            portfolio_value=portfolio_value,
            buying_power=self.cash,
            equity=self.cash + portfolio_value,
            currency="USD",
            is_paper=True,
        )

    def get_positions(self) -> list[PositionInfo]:
        return [
            PositionInfo(
                symbol=symbol,
                quantity=pos["quantity"],
                avg_entry_price=pos["avg_entry_price"],
                market_value=pos["quantity"] * pos["current_price"],
                unrealized_pl=pos["quantity"] * (pos["current_price"] - pos["avg_entry_price"]),
                side="long" if pos["quantity"] > 0 else "short",
            )
            for symbol, pos in self.positions.items()
        ]

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
    ) -> dict:
        """Simulate order execution at given price."""
        self._order_id += 1
        order_id = f"LOCAL_{self._order_id}"

        if side == OrderSide.BUY:
            cost = quantity * price
            if cost > self.cash:
                return {"order_id": order_id, "status": "rejected", "message": "Insufficient funds"}
            self.cash -= cost
            if symbol in self.positions:
                old_qty = self.positions[symbol]["quantity"]
                old_avg = self.positions[symbol]["avg_entry_price"]
                new_qty = old_qty + quantity
                new_avg = (old_qty * old_avg + quantity * price) / new_qty
                self.positions[symbol]["quantity"] = new_qty
                self.positions[symbol]["avg_entry_price"] = new_avg
            else:
                self.positions[symbol] = {
                    "quantity": quantity,
                    "avg_entry_price": price,
                    "current_price": price,
                }
        else:  # sell
            if symbol not in self.positions or self.positions[symbol]["quantity"] < quantity:
                return {"order_id": order_id, "status": "rejected", "message": "Insufficient shares"}
            self.cash += quantity * price
            self.positions[symbol]["quantity"] -= quantity
            if self.positions[symbol]["quantity"] == 0:
                del self.positions[symbol]

        logger.info("LOCAL SIM: %s %s %s @ $%.2f", side.value.upper(), quantity, symbol, price)
        return {"order_id": order_id, "status": "filled", "filled_price": price}


def run_paper_trading(simulate: bool = False) -> None:
    """Run interactive paper trading session."""
    gateway = LocalSimulator() if simulate else AlpacaTradingGateway()

    if not gateway.connect():
        logger.error("Failed to connect")
        sys.exit(1)

    try:
        # Show initial state
        if simulate:
            account = gateway.get_account()
            print("\n" + "=" * 60)
            print("LOCAL SIMULATOR - No real API calls")
            print("=" * 60)
            print(f"  Initial Cash: ${account.cash:,.2f}")
        else:
            show_account_info(gateway)
            show_positions(gateway)

        print("\nPaper trading ready. Type 'help' for commands.")
        print("Type 'quit' to exit.\n")

        while True:
            try:
                cmd = input("paper> ").strip().lower()
            except EOFError:
                break

            if not cmd:
                continue
            elif cmd in ("quit", "exit", "q"):
                break
            elif cmd == "help":
                print("\nCommands:")
                print("  info     - Show account info")
                print("  pos      - Show positions")
                print("  buy      - Buy shares (e.g., 'buy AAPL 10')")
                print("  sell     - Sell shares (e.g., 'sell AAPL 10')")
                print("  quit     - Exit\n")
            elif cmd == "info":
                if simulate:
                    account = gateway.get_account()
                    print(f"\nCash: ${account.cash:,.2f}, Equity: ${account.equity:,.2f}\n")
                else:
                    show_account_info(gateway)
            elif cmd == "pos":
                if simulate:
                    positions = gateway.get_positions()
                    if not positions:
                        print("\nNo positions\n")
                    else:
                        for p in positions:
                            print(f"  {p.symbol}: {p.quantity} shares, P/L: ${p.unrealized_pl:.2f}")
                        print()
                else:
                    show_positions(gateway)
            elif cmd.startswith("buy ") or cmd.startswith("sell "):
                parts = cmd.split()
                if len(parts) != 3:
                    print("Usage: buy/sell SYMBOL QUANTITY")
                    continue
                action, symbol, qty_str = parts
                try:
                    qty = float(qty_str)
                except ValueError:
                    print("Invalid quantity")
                    continue

                symbol = symbol.upper()
                side = OrderSide.BUY if action == "buy" else OrderSide.SELL

                if simulate:
                    # For simulation, use a fixed price (would need real data feed)
                    result = gateway.submit_order(symbol, side, qty, 100.0)
                    print(f"Order {result['status']}: {result.get('message', '')}")
                else:
                    result = gateway.submit_order(
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        order_type=OrderType.MARKET,
                        time_in_force=TimeInForce.DAY,
                    )
                    print(f"Order {result.status}: ID={result.order_id}")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

    finally:
        gateway.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="Paper Trading Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_paper.py                  Connect to Alpaca paper trading
  python run_paper.py --simulate       Run in local simulation mode
  python run_paper.py --info           Show account info and exit
        """,
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in local simulation mode (no API calls)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show account info and exit",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    if args.info:
        gateway = AlpacaTradingGateway()
        if gateway.connect():
            show_account_info(gateway)
            show_positions(gateway)
            gateway.disconnect()
        else:
            sys.exit(1)
    else:
        run_paper_trading(simulate=args.simulate)


if __name__ == "__main__":
    main()
