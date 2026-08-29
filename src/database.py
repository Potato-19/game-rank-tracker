import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import Config


class DatabaseManager:
    """SQLite 数据库管理器，负责建表与排名数据的读写。"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_schema(self, cursor: sqlite3.Cursor) -> None:
        """兼容旧库：若缺少 total_rank 字段则自动追加。"""
        cursor.execute("PRAGMA table_info(daily_rankings)")
        columns = {row[1] for row in cursor.fetchall()}
        if "total_rank" not in columns:
            cursor.execute(
                "ALTER TABLE daily_rankings ADD COLUMN total_rank INTEGER"
            )

    def _init_database(self) -> None:
        """创建 data 目录及数据库表结构。"""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_rankings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        app_id TEXT NOT NULL,
                        country TEXT NOT NULL,
                        chart_type TEXT NOT NULL,
                        rank INTEGER NOT NULL,
                        total_rank INTEGER,
                        fetch_date TEXT NOT NULL,
                        UNIQUE (app_id, country, chart_type, fetch_date)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS apps (
                        app_id TEXT PRIMARY KEY,
                        app_name TEXT NOT NULL,
                        developer TEXT,
                        category TEXT,
                        icon_url TEXT,
                        last_updated TEXT
                    )
                    """
                )
                self._migrate_schema(cursor)
                conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"数据库初始化失败: {exc}") from exc

    def save_rankings(
        self,
        rankings_list: list[dict],
        country: str,
        chart_type: str,
    ) -> None:
        """保存当天游戏榜单快照，同时写入游戏内排名与总榜排名。"""
        fetch_date = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
        now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for item in rankings_list:
                    cursor.execute(
                        """
                        INSERT INTO daily_rankings
                            (app_id, country, chart_type, rank, total_rank, fetch_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(app_id, country, chart_type, fetch_date)
                        DO UPDATE SET
                            rank = excluded.rank,
                            total_rank = excluded.total_rank
                        """,
                        (
                            item["app_id"],
                            country,
                            chart_type,
                            item["rank"],
                            item.get("total_rank"),
                            fetch_date,
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO apps
                            (app_id, app_name, developer, category, icon_url, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["app_id"],
                            item["app_name"],
                            item.get("developer"),
                            item.get("category"),
                            item.get("icon_url"),
                            now,
                        ),
                    )
                conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"保存排名数据失败: {exc}") from exc

    def get_all_apps(self) -> list[dict]:
        """查询 apps 表中的所有应用。"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT app_id, app_name, developer, category, icon_url, last_updated
                    FROM apps
                    ORDER BY app_name
                    """
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            raise RuntimeError(f"查询应用列表失败: {exc}") from exc

    def get_app_history(self, app_id: str) -> list[dict]:
        """查询指定应用的历史排名记录，按日期升序排列。"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, app_id, country, chart_type, rank, total_rank, fetch_date
                    FROM daily_rankings
                    WHERE app_id = ?
                    ORDER BY fetch_date ASC
                    """,
                    (app_id,),
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            raise RuntimeError(f"查询应用历史排名失败: {exc}") from exc
