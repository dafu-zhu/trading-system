import logging
import os

import pandas as pd
import yfinance as yf
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

import utils

logger = logging.getLogger("src.data.providers.yf_provider")
load_dotenv()


class YfinanceProvider:

    def __init__(self, path: Path):
        # directory to store data
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def download(
            self,
            tickers: list[str],
            period: str='7d',
            interval: str='1m',
            store: bool=False
    ) -> Dict[str, pd.DataFrame] | None:
        if not tickers:
            return None

        logger.info("Start downloading...")

        data = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False
        )

        data_dict = {}
        for ticker in tickers:
            ticker_df = data.xs(ticker, level='Ticker', axis=1)
            data_dict[ticker] = ticker_df
            if store:
                file_path = self.path / f"{ticker}.csv"
                ticker_df.to_csv(file_path)
                logger.info(f"Download {ticker} successful!")

        return data_dict


if __name__ == '__main__':
    from logger.logger import setup_logging
    setup_logging()
    root_path = utils.get_root()
    YF_DATA_PATH = os.getenv("YF_TICK_PATH")
    yfp = YfinanceProvider(root_path / Path(YF_DATA_PATH))
    tickers = ['AAPL', 'MSFT']
    yfp.download(tickers=tickers, store=True)