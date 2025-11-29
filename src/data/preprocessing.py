import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List
import utils

logger = logging.getLogger("src.data")

ROOT_PATH = utils.path(end_point='src')
YF_DATA_PATH = ROOT_PATH / "data" / "storage" / "yfinance" / "ticks"

class Preprocessor:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.df = None

    def load(self) -> 'Preprocessor':
        logger.info(f"Loading data from {self.file_path}")
        # Load the CSV file
        self.df = pd.read_csv(self.file_path)
        return self

    def clean(self, index_str: str='Datetime') -> pd.DataFrame:
        """
        Load CSV file and perform basic cleaning operations.
        :param index_str: assign a column name as index
        :return Cleaned DataFrame with Datetime index
        """
        if self.df is not None:
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

        return df

    def add_features(self, features: List[int]):
        # TODO: integrate basic features
        pass