"""
SQLite storage for market data.

Provides persistent storage for OHLCV bars with efficient querying.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from models import Bar, Timeframe

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parents[2] / "data" / "trading.db"


class BarStorage:
    """
    SQLite storage for OHLCV bar data.

    Provides methods to save and retrieve bars with support for
    multiple symbols and timeframes.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize bar storage.

        :param db_path: Path to SQLite database file (default: data/trading.db)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bars (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    timeframe TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    vwap REAL,
                    trade_count INTEGER,
                    UNIQUE(symbol, timestamp, timeframe)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bars_symbol_time
                ON bars(symbol, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bars_symbol_timeframe
                ON bars(symbol, timeframe, timestamp)
            """)
            conn.commit()
            logger.debug("Database initialized at %s", self.db_path)

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_bars(self, bars: list[Bar]) -> int:
        """
        Save bars to the database.

        Uses INSERT OR REPLACE to handle duplicates.

        :param bars: List of Bar objects to save
        :return: Number of bars saved
        """
        if not bars:
            return 0

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO bars
                (symbol, timestamp, timeframe, open, high, low, close, volume, vwap, trade_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        bar.symbol,
                        bar.timestamp,
                        bar.timeframe.value,
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.volume,
                        bar.vwap,
                        bar.trade_count,
                    )
                    for bar in bars
                ],
            )
            conn.commit()
            logger.debug("Saved %d bars", len(bars))
            return len(bars)

    def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """
        Get bars for a symbol within a time range.

        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :param start: Start datetime (inclusive)
        :param end: End datetime (exclusive)
        :return: List of Bar objects sorted by timestamp
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT symbol, timestamp, timeframe, open, high, low, close,
                       volume, vwap, trade_count
                FROM bars
                WHERE symbol = ? AND timeframe = ? AND timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
                """,
                (symbol, timeframe.value, start, end),
            )
            return [self._row_to_bar(row) for row in cursor.fetchall()]

    def _parse_timestamp(self, ts: str | datetime) -> Optional[datetime]:
        """Parse timestamp from SQLite, handling both string and datetime formats."""
        if ts is None:
            return None
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> Optional[datetime]:
        """
        Get the latest timestamp for a symbol/timeframe combination.

        Useful for determining where to resume data fetching.

        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :return: Latest timestamp or None if no data
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT MAX(timestamp) as latest
                FROM bars
                WHERE symbol = ? AND timeframe = ?
                """,
                (symbol, timeframe.value),
            )
            row = cursor.fetchone()
            return self._parse_timestamp(row["latest"]) if row else None

    def get_earliest_timestamp(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> Optional[datetime]:
        """
        Get the earliest timestamp for a symbol/timeframe combination.

        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :return: Earliest timestamp or None if no data
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT MIN(timestamp) as earliest
                FROM bars
                WHERE symbol = ? AND timeframe = ?
                """,
                (symbol, timeframe.value),
            )
            row = cursor.fetchone()
            return self._parse_timestamp(row["earliest"]) if row else None

    def has_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> bool:
        """
        Check if data exists for a symbol/timeframe in a date range.

        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :param start: Start datetime
        :param end: End datetime
        :return: True if any data exists in the range
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM bars
                WHERE symbol = ? AND timeframe = ? AND timestamp >= ? AND timestamp < ?
                """,
                (symbol, timeframe.value, start, end),
            )
            row = cursor.fetchone()
            return row["count"] > 0

    def get_bar_count(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> int:
        """
        Get total bar count for a symbol/timeframe.

        :param symbol: Stock symbol
        :param timeframe: Bar timeframe
        :return: Number of bars stored
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM bars
                WHERE symbol = ? AND timeframe = ?
                """,
                (symbol, timeframe.value),
            )
            row = cursor.fetchone()
            return row["count"]

    def get_symbols(self) -> list[str]:
        """
        Get all symbols in the database.

        :return: List of unique symbols
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT symbol FROM bars ORDER BY symbol")
            return [row["symbol"] for row in cursor.fetchall()]

    def get_timeframes(self, symbol: str) -> list[Timeframe]:
        """
        Get all timeframes available for a symbol.

        :param symbol: Stock symbol
        :return: List of available timeframes
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT timeframe FROM bars
                WHERE symbol = ? ORDER BY timeframe
                """,
                (symbol,),
            )
            return [Timeframe(row["timeframe"]) for row in cursor.fetchall()]

    def delete_bars(
        self,
        symbol: str,
        timeframe: Optional[Timeframe] = None,
    ) -> int:
        """
        Delete bars for a symbol.

        :param symbol: Stock symbol
        :param timeframe: Optional timeframe (delete all if None)
        :return: Number of bars deleted
        """
        with self._get_connection() as conn:
            if timeframe:
                cursor = conn.execute(
                    "DELETE FROM bars WHERE symbol = ? AND timeframe = ?",
                    (symbol, timeframe.value),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM bars WHERE symbol = ?",
                    (symbol,),
                )
            conn.commit()
            deleted = cursor.rowcount
            logger.info("Deleted %d bars for %s", deleted, symbol)
            return deleted

    def _row_to_bar(self, row: sqlite3.Row) -> Bar:
        """Convert a database row to a Bar object."""
        return Bar(
            symbol=row["symbol"],
            timestamp=self._parse_timestamp(row["timestamp"]),  # type: ignore
            timeframe=Timeframe(row["timeframe"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            vwap=row["vwap"],
            trade_count=row["trade_count"],
        )

    def vacuum(self) -> None:
        """
        Optimize the database by running VACUUM.

        Call periodically after large deletions.
        """
        with self._get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("Database vacuumed")

    def get_stats(self) -> dict:
        """
        Get storage statistics.

        :return: Dictionary with storage statistics
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_bars,
                    COUNT(DISTINCT symbol) as symbols,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest
                FROM bars
                """
            )
            row = cursor.fetchone()
            return {
                "total_bars": row["total_bars"],
                "symbols": row["symbols"],
                "earliest": row["earliest"],
                "latest": row["latest"],
                "db_path": str(self.db_path),
                "db_size_mb": self.db_path.stat().st_size / (1024 * 1024)
                if self.db_path.exists()
                else 0,
            }
