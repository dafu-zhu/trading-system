import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional

from pandas import RangeIndex

import utils
from data.features.basic import BasicFeatures, ColumnMapping

logger = logging.getLogger("src.data")

ROOT_PATH = utils.path(end_point='src')
YF_DATA_PATH = ROOT_PATH / "data" / "storage" / "yfinance" / "ticks"

class Preprocessor:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.df = None
        self.cleaned = False

    def load(self) -> 'Preprocessor':
        logger.info(f"Loading data from {self.file_path}")
        # Load the CSV file
        self.df = pd.read_csv(self.file_path)
        return self

    def clean(self, index_str: str='Datetime') -> 'Preprocessor':
        """
        Load CSV file and perform basic cleaning operations.
        :param index_str: assign a column name as index
        :return Cleaned DataFrame with Datetime index
        """
        if self.df is None:
            self.load()

        df = self.df
        initial_rows = len(df)
        logger.debug(f"Initial shape: {df.shape}")

        # Remove duplicate rows
        df = df.drop_duplicates()
        duplicates_removed = initial_rows - len(df)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rows")

        # Convert Datetime column to datetime type
        if isinstance(df.index, pd.RangeIndex):
            df[index_str] = pd.to_datetime(df[index_str])
            df = df.set_index(index_str)

        # Sort chronologically
        df = df.sort_index()

        # Remove rows with missing values
        missing_before = df.isna().sum().sum()
        df = df.dropna()
        missing_removed = missing_before - df.isna().sum().sum()
        if missing_removed > 0:
            logger.info(f"Removed {missing_removed} missing values")

        logger.info(f"Final shape after cleaning: {df.shape}")

        self.df = df
        self.cleaned = True
        return self

    def add_features(
            self,
            features: List[str],
            windows: Optional[List[int]] = None,
            col_mapping: Optional[ColumnMapping] = None,
            **feature_kwargs
    ) -> 'Preprocessor':
        """
        Add
        :param features:
        :param windows:
        :param col_mapping:
        :param feature_kwargs:
        :return:
        """
        if self.df is None or not self.cleaned:
            self.load().clean()

        self.df = BasicFeatures.calculate(
            self.df,
            features=features,
            windows=windows,
            col_mapping=col_mapping,
            **feature_kwargs
        )
        self.cleaned = False
        return self

    @property
    def get_data(self):
        return self.df


if __name__ == '__main__':
    # Example
    df = (
        Preprocessor(YF_DATA_PATH / "AAPL.csv")
        .load()
        .clean()
        .add_features(
            features=['returns', 'rsi', 'moving_average'],
            windows=[10, 50, 200],
            rsi_window=21
        )
        .clean()
        .get_data
    )
    print(df.head())
    """
    Expected output
                                Adj Close       Close  ...     sma_200     ema_200
    Datetime                                           ...                        
    2025-11-19 17:49:00+00:00  270.019989  270.019989  ...  270.148461  269.726213
    2025-11-19 17:50:00+00:00  270.234985  270.234985  ...  270.164986  269.731276
    2025-11-19 17:51:00+00:00  270.179993  270.179993  ...  270.182931  269.735741
    2025-11-19 17:52:00+00:00  270.394989  270.394989  ...  270.202156  269.742300
    2025-11-19 17:53:00+00:00  270.510010  270.510010  ...  270.223906  269.749939
    """