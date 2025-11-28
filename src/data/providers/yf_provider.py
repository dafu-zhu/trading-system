import yfinance as yf
from pathlib import Path

yf_path = Path(__file__).parent.parent / "storage/historical/yfinance"

# data = yf.download(tickers='AAPL', period='7d', interval='1m')

# data.to_csv('market_data.csv')
