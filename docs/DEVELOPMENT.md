## 🎯 Top Priority APIs from Alpaca

### Trading API - Paper Trading ⭐⭐⭐

Why it's critical:
- Base URL: https://paper-api.alpaca.markets
- Free $100k simulated account (resets available)
- Real-time order simulation with actual market data
- Anyone globally can create account with just email
- Supports margin, short selling, extended hours
- Does NOT simulate dividends or regulatory fees

Key Details:
- Uses same API spec as live trading
- Separate API keys for paper vs live
- IEX real-time data included free

### Trading API - Placing Orders ⭐⭐⭐

Endpoints you'll use:
- POST /v2/orders - Submit orders
- GET /v2/orders - List orders
- DELETE /v2/orders/{order_id} - Cancel orders
- PATCH /v2/orders/{order_id} - Replace orders

Order Types Supported:
- Market, Limit, Stop, Stop-Limit
- Bracket orders (entry + take-profit + stop-loss)
- OCO (One-Cancels-Other)
- Trailing stop orders

Time in Force:
- day - Day orders (required for paper trading)
- gtc - Good till cancelled
- ioc - Immediate or cancel
- Extended hours support with extended_hours: true

### Market Data API - WebSocket Streaming ⭐⭐⭐

For Real-Time Data Feed:
- URL: wss://stream.data.alpaca.markets/v2/iex
- Test stream: wss://stream.data.alpaca.markets/v2/test (use symbol "FAKEPACA")

Channels:
- trades - Real-time trade executions
- quotes - Real-time bid/ask quotes
- bars - Real-time 1-min bars
- dailyBars - Daily aggregates

Authentication:
- HTTP headers: APCA-API-KEY-ID, APCA-API-SECRET-KEY
- Or auth message after connection

### Market Data API - Historical Data ⭐⭐

For Backtesting & Historical Analysis:
- GET /v2/stocks/bars - Historical OHLCV bars
- GET /v2/stocks/quotes - Historical quotes
- GET /v2/stocks/trades - Historical trades
- Timeframes: 1Min, 5Min, 15Min, 1Hour, 1Day

SDKs Available:
- Python: pip install alpaca-py
- JavaScript, Go, C#

### Trading API - Account & Positions ⭐⭐

Monitor Your Portfolio:
- GET /v2/account - Account info, buying power, equity
- GET /v2/positions - All open positions
- GET /v2/positions/{symbol} - Specific position
- DELETE /v2/positions - Close all positions
- DELETE /v2/positions/{symbol} - Close specific position

### Supporting APIs ⭐

- GET /v2/assets - Get tradable symbols
- GET /v2/clock - Market open/close status
- GET /v2/calendar - Trading calendar
- GET /v2/account/activities - Account activity history

### 📋 Recommended Implementation Order:

1. Start with Paper Trading setup - Get API keys from dashboard
2. Implement WebSocket streaming - Real-time market data feed
3. Build order management - Place, cancel, and track orders
4. Add account monitoring - Track positions and P&L
5. Integrate historical data - For backtesting and analysis

### 🔑 Key Endpoints Summary:

Paper Trading Base URL: https://paper-api.alpaca.markets
Market Data Base URL: https://data.alpaca.markets
WebSocket Stream: wss://stream.data.alpaca.markets/v2/iex

Core endpoints:
- POST /v2/orders
- GET /v2/account
- GET /v2/positions
- WebSocket: subscribe to trades/quotes/bars
- GET /v2/stocks/bars (historical)

The Paper Trading, Orders, and WebSocket Market Data sections are your foundation. Everything else supports these core functions.