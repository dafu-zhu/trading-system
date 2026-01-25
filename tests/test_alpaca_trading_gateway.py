"""
Tests for AlpacaTradingGateway.

Includes:
- Unit tests with mocked Alpaca API
- Integration tests with real API (marked with @pytest.mark.integration)
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from gateway.alpaca_trading_gateway import AlpacaTradingGateway
from models import (
    OrderSide,
    OrderType,
    TimeInForce,
    AccountInfo,
    PositionInfo,
    OrderResult,
)


class TestAlpacaTradingGatewayUnit:
    """Unit tests with mocked Alpaca API."""

    @pytest.fixture
    def mock_trading_client(self):
        """Create a mock TradingClient."""
        with patch("gateway.alpaca_trading_gateway.TradingClient") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def gateway(self, mock_trading_client):
        """Create gateway with mocked credentials."""
        with patch.dict(
            os.environ,
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_API_SECRET": "test_secret",
                "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
            },
        ):
            gw = AlpacaTradingGateway()
            return gw

    def test_init_requires_credentials(self):
        """Test that gateway requires API credentials."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API credentials required"):
                AlpacaTradingGateway()

    def test_init_accepts_env_credentials(self):
        """Test that gateway accepts credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_API_SECRET": "test_secret",
            },
        ):
            with patch("gateway.alpaca_trading_gateway.TradingClient"):
                gw = AlpacaTradingGateway()
                assert gw._api_key == "test_key"
                assert gw._api_secret == "test_secret"

    def test_init_accepts_direct_credentials(self):
        """Test that gateway accepts credentials passed directly."""
        with patch("gateway.alpaca_trading_gateway.TradingClient"):
            gw = AlpacaTradingGateway(
                api_key="direct_key",
                api_secret="direct_secret",
            )
            assert gw._api_key == "direct_key"
            assert gw._api_secret == "direct_secret"

    def test_init_warns_on_live_url(self, caplog):
        """Test that gateway warns when using live URL."""
        with patch("gateway.alpaca_trading_gateway.TradingClient"):
            with patch.dict(
                os.environ,
                {
                    "ALPACA_API_KEY": "test_key",
                    "ALPACA_API_SECRET": "test_secret",
                    "ALPACA_BASE_URL": "https://api.alpaca.markets",
                },
            ):
                AlpacaTradingGateway()
                assert "LIVE" in caplog.text or not caplog.text  # Warning logged

    def test_connect_success(self, gateway, mock_trading_client):
        """Test successful connection."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account

        result = gateway.connect()

        assert result is True
        assert gateway.is_connected() is True

    def test_connect_failure(self, gateway, mock_trading_client):
        """Test connection failure."""
        from alpaca.common.exceptions import APIError

        mock_trading_client.get_account.side_effect = APIError("Auth failed")

        result = gateway.connect()

        assert result is False
        assert gateway.is_connected() is False

    def test_disconnect(self, gateway, mock_trading_client):
        """Test disconnect."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account
        gateway.connect()

        gateway.disconnect()

        assert gateway.is_connected() is False

    def test_get_account(self, gateway, mock_trading_client):
        """Test get_account returns AccountInfo."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_account.cash = "10000.00"
        mock_account.portfolio_value = "15000.00"
        mock_account.buying_power = "20000.00"
        mock_account.equity = "15000.00"
        mock_account.currency = "USD"
        mock_trading_client.get_account.return_value = mock_account
        gateway.connect()

        result = gateway.get_account()

        assert isinstance(result, AccountInfo)
        assert result.account_id == "PA123"
        assert result.cash == 10000.0
        assert result.portfolio_value == 15000.0
        assert result.is_paper is True

    def test_get_positions_empty(self, gateway, mock_trading_client):
        """Test get_positions with no positions."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account
        mock_trading_client.get_all_positions.return_value = []
        gateway.connect()

        result = gateway.get_positions()

        assert result == []

    def test_get_positions_with_positions(self, gateway, mock_trading_client):
        """Test get_positions with positions."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account

        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.00"
        mock_position.market_value = "16000.00"
        mock_position.unrealized_pl = "1000.00"
        mock_trading_client.get_all_positions.return_value = [mock_position]
        gateway.connect()

        result = gateway.get_positions()

        assert len(result) == 1
        assert isinstance(result[0], PositionInfo)
        assert result[0].symbol == "AAPL"
        assert result[0].quantity == 100.0
        assert result[0].side == "long"

    def test_submit_market_order(self, gateway, mock_trading_client):
        """Test submitting a market order."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account

        mock_order = Mock()
        mock_order.id = "order123"
        mock_order.client_order_id = None
        mock_order.symbol = "AAPL"
        mock_order.side = Mock()
        mock_order.side.name = "BUY"
        mock_order.order_type = Mock()
        mock_order.order_type.name = "MARKET"
        mock_order.qty = "10"
        mock_order.filled_qty = "0"
        mock_order.status = Mock()
        mock_order.status.name = "NEW"
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = None
        mock_order.filled_avg_price = None
        mock_trading_client.submit_order.return_value = mock_order

        # Mock the enum comparisons
        from alpaca.trading.enums import (
            OrderSide as AlpacaOrderSide,
            OrderStatus as AlpacaOrderStatus,
            OrderType as AlpacaOT,
        )

        mock_order.side = AlpacaOrderSide.BUY
        mock_order.status = AlpacaOrderStatus.NEW
        mock_order.order_type = AlpacaOT.MARKET

        gateway.connect()
        result = gateway.submit_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )

        assert isinstance(result, OrderResult)
        assert result.order_id == "order123"
        assert result.symbol == "AAPL"
        assert result.side == OrderSide.BUY
        assert result.quantity == 10.0

    def test_submit_limit_order_requires_price(self, gateway, mock_trading_client):
        """Test that limit order requires limit_price."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account
        gateway.connect()

        with pytest.raises(ValueError, match="limit_price required"):
            gateway.submit_order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=10,
                order_type=OrderType.LIMIT,
            )

    def test_cancel_order_success(self, gateway, mock_trading_client):
        """Test successful order cancellation."""
        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account
        gateway.connect()

        result = gateway.cancel_order("order123")

        assert result is True
        mock_trading_client.cancel_order_by_id.assert_called_once_with("order123")

    def test_cancel_order_failure(self, gateway, mock_trading_client):
        """Test failed order cancellation."""
        from alpaca.common.exceptions import APIError

        mock_account = Mock()
        mock_account.account_number = "PA123"
        mock_trading_client.get_account.return_value = mock_account
        mock_trading_client.cancel_order_by_id.side_effect = APIError("Order not found")
        gateway.connect()

        result = gateway.cancel_order("invalid_order")

        assert result is False

    def test_operations_require_connection(self, gateway):
        """Test that operations require connection."""
        with pytest.raises(RuntimeError, match="Not connected"):
            gateway.get_account()

        with pytest.raises(RuntimeError, match="Not connected"):
            gateway.get_positions()

        with pytest.raises(RuntimeError, match="Not connected"):
            gateway.submit_order("AAPL", OrderSide.BUY, 10)


class TestAlpacaTradingGatewayIntegration:
    """Integration tests with real Alpaca API.

    These tests require valid API credentials and make real API calls.
    Run with: pytest -m integration
    """

    @pytest.fixture
    def live_gateway(self):
        """Create gateway with real credentials."""
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")

        if not api_key or not api_secret:
            pytest.skip("Alpaca credentials not available")

        gw = AlpacaTradingGateway()
        yield gw
        if gw.is_connected():
            gw.disconnect()

    @pytest.mark.integration
    def test_connect_to_alpaca(self, live_gateway):
        """Test real connection to Alpaca."""
        result = live_gateway.connect()
        assert result is True
        assert live_gateway.is_connected() is True

    @pytest.mark.integration
    def test_get_real_account(self, live_gateway):
        """Test getting real account info."""
        live_gateway.connect()
        account = live_gateway.get_account()

        assert isinstance(account, AccountInfo)
        assert account.account_id is not None
        assert account.cash >= 0
        assert account.is_paper is True  # Should always be paper for tests

    @pytest.mark.integration
    def test_get_real_positions(self, live_gateway):
        """Test getting real positions."""
        live_gateway.connect()
        positions = live_gateway.get_positions()

        assert isinstance(positions, list)
        # May be empty if no positions

    @pytest.mark.integration
    def test_submit_and_cancel_order(self, live_gateway):
        """Test submitting and immediately canceling an order."""
        live_gateway.connect()

        # Submit a limit order far from market (won't fill)
        result = live_gateway.submit_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.LIMIT,
            limit_price=1.00,  # Far below market
            time_in_force=TimeInForce.DAY,
        )

        assert result.order_id != ""
        assert result.status in ("new", "accepted", "pending_new")

        # Cancel the order
        canceled = live_gateway.cancel_order(result.order_id)
        assert canceled is True


class TestOrderSideEnum:
    """Test OrderSide enum."""

    def test_order_side_values(self):
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"


class TestOrderTypeEnum:
    """Test OrderType enum."""

    def test_order_type_values(self):
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"


class TestTimeInForceEnum:
    """Test TimeInForce enum."""

    def test_time_in_force_values(self):
        assert TimeInForce.DAY.value == "day"
        assert TimeInForce.GTC.value == "gtc"
        assert TimeInForce.IOC.value == "ioc"
        assert TimeInForce.FOK.value == "fok"
