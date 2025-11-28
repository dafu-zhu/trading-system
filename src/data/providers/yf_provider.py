import yfinance as yf
from pathlib import Path

yf_path = Path(__file__).parent.parent / "storage/historical/yfinance"
data = yf.download(
    tickers='AAPL',
    start="2025",
    interval='1m',
    auto_adjust=False,
    progress=False
)
print(data)


# data.to_csv('market_data.csv')
