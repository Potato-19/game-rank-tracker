import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.config import Config

BEIJING_TZ = ZoneInfo("Asia/Shanghai")

CHART_LABELS = {
    "top-free": "免费游戏榜",
    "top-grossing": "畅销游戏榜",
}

# SQL 中用于筛选游戏类应用的条件
_GAME_CATEGORY_SQL = ", ".join(f"'{cat}'" for cat in Config.GAME_CATEGORIES)


class GameAnalyzer:
    """榜单数据分析器，提供排名查询与趋势对比能力。"""

    def __init__(self, db_manager):
        """注入数据库管理器实例。"""
        self.db_manager = db_manager

    def _today(self) -> str:
        """返回北京时间今日日期字符串。"""
        return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    def _yesterday(self) -> str:
        """返回北京时间昨日日期字符串。"""
        yesterday = datetime.now(BEIJING_TZ).date() - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")

    def _query_rankings(
        self,
        country: str,
        chart_type: str,
        fetch_date: str,
        limit: int | None = None,
    ) -> list[dict]:
        """查询指定日期的游戏榜单，关联应用维度信息。"""
        query_limit = limit or Config.REPORT_LIMIT
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT dr.rank, dr.total_rank, dr.app_id, a.app_name, a.developer
                    FROM daily_rankings dr
                    JOIN apps a ON dr.app_id = a.app_id
                    WHERE dr.country = ? AND dr.chart_type = ? AND dr.fetch_date = ?
                      AND a.category IN ({_GAME_CATEGORY_SQL})
                    ORDER BY dr.rank ASC
                    LIMIT ?
                    """,
                    (country, chart_type, fetch_date, query_limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def get_today_date(self) -> str:
        """返回今日日期，供报告文件命名使用。"""
        return self._today()

    def has_today_data(self, country: str, chart_type: str) -> bool:
        """检查指定榜单是否存在今日数据。"""
        return len(self._query_rankings(country, chart_type, self._today(), limit=1)) > 0

    def has_yesterday_data(self, country: str, chart_type: str) -> bool:
        """检查指定榜单是否存在昨日数据。"""
        return (
            len(self._query_rankings(country, chart_type, self._yesterday(), limit=1)) > 0
        )

    def get_today_top(
        self,
        country: str,
        chart_type: str,
        limit: int | None = None,
    ) -> list[dict]:
        """查询指定国家、指定榜单今日排名前 N 的游戏。"""
        query_limit = limit or Config.REPORT_LIMIT
        rows = self._query_rankings(
            country, chart_type, self._today(), limit=query_limit
        )
        return [
            {
                "rank": row["rank"],
                "total_rank": row["total_rank"],
                "app_name": row["app_name"] or "未知应用",
                "developer": row["developer"] or "未知开发者",
                "app_id": row["app_id"],
            }
            for row in rows
        ]

    def get_rank_changes(self, app_id: str, days: int = 1) -> list[dict] | None:
        """
        查询某个应用最近 N 天的排名变化。
        历史数据不足时返回 None（数据积累中）。
        """
        history = self.db_manager.get_app_history(app_id)
        if not history:
            return None

        grouped: dict[tuple[str, str], list[dict]] = {}
        for record in history:
            key = (record["country"], record["chart_type"])
            grouped.setdefault(key, []).append(record)

        changes: list[dict] = []
        for (country, chart_type), records in grouped.items():
            records.sort(key=lambda item: item["fetch_date"])
            if len(records) < 2:
                continue

            previous = records[-2]
            current = records[-1]

            prev_date = datetime.strptime(previous["fetch_date"], "%Y-%m-%d").date()
            curr_date = datetime.strptime(current["fetch_date"], "%Y-%m-%d").date()
            if (curr_date - prev_date).days < days:
                continue

            rank_change = previous["rank"] - current["rank"]
            changes.append(
                {
                    "country": country,
                    "chart_type": chart_type,
                    "previous_rank": previous["rank"],
                    "current_rank": current["rank"],
                    "rank_change": rank_change,
                    "previous_date": previous["fetch_date"],
                    "current_date": current["fetch_date"],
                }
            )

        if not changes:
            return None
        return changes

    def get_rising_stars(
        self,
        country: str,
        chart_type: str,
        top_n: int = 5,
    ) -> list[dict]:
        """找出游戏榜排名上升最快的应用（对比昨日与今日）。"""
        today = self._today()
        yesterday = self._yesterday()

        today_rows = self._query_rankings(country, chart_type, today)
        yesterday_rows = self._query_rankings(country, chart_type, yesterday)

        if not yesterday_rows:
            chart_label = CHART_LABELS.get(chart_type, chart_type)
            print(f"提示：{country}/{chart_label} 暂无昨日数据，无法计算上升榜单。")
            return []

        yesterday_map = {row["app_id"]: row for row in yesterday_rows}
        rising: list[dict] = []

        for row in today_rows:
            prev = yesterday_map.get(row["app_id"])
            if not prev:
                continue

            rank_change = prev["rank"] - row["rank"]
            if rank_change <= 0:
                continue

            rising.append(
                {
                    "app_id": row["app_id"],
                    "app_name": row["app_name"] or "未知应用",
                    "developer": row["developer"] or "未知开发者",
                    "today_rank": row["rank"],
                    "yesterday_rank": prev["rank"],
                    "rank_change": rank_change,
                }
            )

        rising.sort(key=lambda item: item["rank_change"], reverse=True)
        return rising[:top_n]

    def get_new_entries(
        self,
        country: str,
        chart_type: str,
        top_n: int = 5,
    ) -> list[dict]:
        """找出今日新进入游戏榜前 N 的应用（昨日不在榜内）。"""
        today = self._today()
        yesterday = self._yesterday()

        today_rows = self._query_rankings(country, chart_type, today)
        yesterday_rows = self._query_rankings(country, chart_type, yesterday)

        if not yesterday_rows:
            return []

        yesterday_ids = {row["app_id"] for row in yesterday_rows}
        new_entries: list[dict] = []

        for row in today_rows:
            if row["app_id"] in yesterday_ids:
                continue
            new_entries.append(
                {
                    "app_id": row["app_id"],
                    "app_name": row["app_name"] or "未知应用",
                    "developer": row["developer"] or "未知开发者",
                    "rank": row["rank"],
                    "total_rank": row["total_rank"],
                }
            )

        return new_entries[:top_n]
