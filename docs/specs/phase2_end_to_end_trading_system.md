# Project - End to End Trading System

**Due: Mon Nov 24, 2025 11:59pm**

**Attempt 1** - Review Feedback

**Unlimited Attempts Allowed**

---

## 📊 Part 1: Data Download and Preparation

### ✅ Step 1: Download Intraday Market Data

**Objective:** Acquire historical intraday data for a selected equity or cryptocurrency.

**Requirements:**

- Use yfinance for equities (e.g., AAPL).
- Use a crypto API (e.g., Binance) for cryptocurrencies.
- Save data as CSV with columns: Datetime, Open, High, Low, Close, Volume.

**Deliverable:**

- A CSV file containing intraday market data for the chosen asset.

**Example (Equity):**

```python
import yfinance as yf

data = yf.download(tickers='AAPL', period='7d', interval='1m')

data.to_csv('market_data.csv')
```

Download data at `data/providers/yf_provider.py`, store at `data/storage/yfinance/ticks`.

---

### 🔧 Step 2: Clean and Organize Data

**Objective:** Prepare the raw data for modeling and strategy development.

**Requirements:**

- Remove missing or duplicate rows.
- Set Datetime as index and sort chronologically.
- Add derived features (e.g., returns, moving averages).

**Deliverable:**

- A cleaned pandas DataFrame ready for analysis.

**Example:**

```python
import pandas as pd

data = pd.read_csv('market_data.csv')

data.dropna(inplace=True)

data.set_index('Datetime', inplace=True)

data.sort_index(inplace=True)
```

Load and clean data in `Preprocessor` class, also provide `add_features` method. Features are calculated under 
`features/`. Make a parent class for `BasicFeatures` after more feature classes are created. 

---

### 🧠 Step 3: Create a Trading Strategy

**Objective:** Design a trading strategy using the cleaned data. The approach is flexible and user-defined.

**Requirements:**

- Implement a strategy using one or more of the following approaches:
  - **Momentum-based:** Trade based on recent price trends.
  - **Moving Average Crossover:** Use short- and long-term averages to generate signals.
  - **Signal Generation Models:** Use statistical or machine learning models.
  - **Sentiment Analysis:** Incorporate external data like news or social media.
- Define clear entry/exit rules and position sizing logic.

**Deliverable:**

- A Python class that encapsulates the strategy logic and exposes methods to generate buy/sell signals from input data.

Implemented a `MACDStrategy` class.

---

## 🔄 Part 2: Backtester Framework

### 🧩 Step 1: Gateway for Data Ingestion

**Objective:** Simulate live market data feed from historical files.

**Requirements:**

- Read cleaned CSV files from Part 1.
- Stream data row-by-row to mimic real-time updates.

**Implementation Target:**

- A **Gateway** class that reads and feeds market data into the system incrementally.

Load data processed by `Preprocessor`, yield market data point one-by-one.

---

### 📈 Step 2: Order Book Implementation

**Objective:** Manage and match bid/ask orders using efficient data structures.

**Requirements:**

- Use heaps or priority queues to store orders.
- Match orders based on price-time priority.
- Support order addition, modification, and cancellation.

**Implementation Target:**

- An **OrderBook** class with methods for order management and matching.



---

### 🚦 Step 3: Order Manager & Gateway

**Objective:** Validate and record orders before execution.

**Requirements:**

- **OrderManager** - Implement checks for capital sufficiency and risk limits.
  - Capital sufficiency should check if enough capital exists to execute the order.
  - Risk limits should check orders per minute and if executing the order would exceed total buy or total sell position limits.
- **Gateway** - Write all orders to a file for audit and analysis. This should include when orders are sent, modified, cancelled or filled.

**Implementation Target:**

- An **OrderManager** class for validation and a **Gateway** class for logging orders.

---

### ⚙️ Step 4: Matching Engine Simulator

**Objective:** Simulate realistic order execution outcomes.

**Requirements:**

- Randomly determine whether orders are filled, partially filled, or canceled.
  - There are no specific requirements on how many orders should be partially filled or rejected.
- Return execution details for each order.

**Implementation Target:**

- A **MatchingEngine** class that simulates order matching and execution outcomes.

---

## 🔍 Part 3: Strategy Backtesting

### 🎯 Objective:

Evaluate the performance of your trading strategy using historical market data to simulate real-world execution.

### ✅ Requirements:

**Simulation Execution:**

- Feed historical data through the Gateway to simulate a live environment.
- Generate and process orders based on strategy signals.
- Use the Matching Engine to simulate fills, partial fills, and cancellations.

**Performance Tracking:**

- Record executed trades, timestamps, prices, and volumes.
- Calculate key metrics: P&L, Sharpe ratio, drawdown, win/loss ratio, etc.

**Reporting:**

- Visualize equity curve, trade distribution, and performance statistics.
- Compare strategy variants and parameter sensitivity.

### 📚 Implementation Target:

- Integrate the backtester components into the **user-defined strategy class** from Part 1.

---

## 📝 Part 4: Alpaca Trading Challenge

### ⚠️ Key Reminders

- **Do not add real money to your Alpaca account.**
- **Do not share your API keys.**
- Keep it simple if you're short on time.

---

### 📝 Step 1: Create an Alpaca Account

- Sign up at alpaca.markets.
- Complete identity verification and confirm your email.
- Log in and explore the dashboard.
- (Optional) Enable two-factor authentication.

---

### 💻 Step 2: Configure Paper Trading

- Navigate to **Paper Overview**.
- Review your starting equity and buying power.
- Use the **Reset** button to restore virtual funds.
- Explore the interface for placing orders and tracking performance.

---

### 🔑 Step 3: Obtain API Keys

- Locate your **API Key ID** and **Secret Key** in account settings.
- Use **paper trading keys** only.
- Keep keys secure and test them with basic API calls.

---

### 📊 Step 4: Retrieve Market Data

- Choose your asset (stock or crypto).

**Install Alpaca SDK:**

```bash
pip install alpaca-trade-api
```

**Sample usage:**

```python
import alpaca_trade_api as tradeapi

api = tradeapi.REST('your_api_key', 'your_api_secret', 'https://paper-api.alpaca.markets')

data = api.get_barset('AAPL', '1Min', limit=1).df['AAPL']
```

- Review Alpaca's API docs and GitHub for more endpoints.

---

### 💾 Step 5: Save Market Data

- Choose storage: flat files (CSV, Pickle) or databases (SQLite, PostgreSQL).
- Organize by asset and timeframe.
- Handle timestamps and timezones accurately.
- Automate updates and clean data for integrity.

---

### 🧠 Step 6: Use Your Strategy from Part 1

- Implement the trading strategy you developed in **Part 1** of the project.
- This strategy should generate buy/sell signals and integrate with your Alpaca-connected system.
- No new strategy is required—focus on refining and deploying the one you've already built.
