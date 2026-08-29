import time

import requests

from src.config import Config


class AppStoreCrawler:
    """App Store RSS 游戏榜单数据抓取器。"""

    RSS_V1_GAME_FEEDS = {
        "top-free": "topfreeapplications",
        "top-grossing": "topgrossingapplications",
    }
    GAME_GENRE_ID = 6014
    RSS_V2_OVERALL_URL = (
        "https://rss.applemarketingtools.com/api/v2"
        "/{country}/apps/{chart_type}/{limit}/apps.json"
    )
    USER_AGENT = "GameRankTracker/1.0 (App Store Ranking Data Tool)"

    def __init__(self, db_manager):
        """初始化抓取器，注入数据库管理器实例。"""
        self.db_manager = db_manager

    def _parse_v1_entries(self, entries: list) -> list[dict]:
        """解析 iTunes RSS v1 entry 列表为统一结构。"""
        items: list[dict] = []
        for entry in entries:
            images = entry.get("im:image") or []
            category_info = entry.get("category", {}).get("attributes", {})
            category = category_info.get("label", "") or "游戏"

            items.append(
                {
                    "app_id": str(entry["id"]["attributes"]["im:id"]),
                    "app_name": entry.get("im:name", {}).get("label", ""),
                    "developer": entry.get("im:artist", {}).get("label", ""),
                    "category": category,
                    "icon_url": images[-1]["label"] if images else "",
                }
            )
        return items

    def _fetch_game_chart_v1(
        self,
        country: str,
        chart_type: str,
        limit: int,
        headers: dict,
    ) -> list[dict] | None:
        """拉取指定类型的游戏榜（genre=6014）。"""
        feed_name = self.RSS_V1_GAME_FEEDS[chart_type]
        url = (
            f"https://itunes.apple.com/{country}/rss/"
            f"{feed_name}/limit={limit}/genre={self.GAME_GENRE_ID}/json"
        )

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            entries = data.get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
        except (requests.RequestException, ValueError):
            return None

        return self._parse_v1_entries(entries)

    def _fetch_overall_v1(
        self,
        country: str,
        chart_type: str,
        limit: int,
        headers: dict,
    ) -> list[str] | None:
        """拉取 App 总榜 app_id 列表（iTunes v1）。"""
        feed_name = self.RSS_V1_GAME_FEEDS[chart_type]
        url = f"https://itunes.apple.com/{country}/rss/{feed_name}/limit={limit}/json"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            entries = data.get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
        except (requests.RequestException, ValueError):
            return None

        return [str(entry["id"]["attributes"]["im:id"]) for entry in entries]

    def _fetch_overall_v2(
        self,
        country: str,
        chart_type: str,
        limit: int,
        headers: dict,
    ) -> list[str] | None:
        """拉取 App 总榜 app_id 列表（RSS v2，仅 top-free 可用）。"""
        url = self.RSS_V2_OVERALL_URL.format(
            country=country,
            chart_type=chart_type,
            limit=limit,
        )

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("feed", {}).get("results", [])
        except (requests.RequestException, ValueError):
            return None

        return [str(item["id"]) for item in results]

    def _build_overall_rank_map(
        self,
        country: str,
        chart_type: str,
        limit: int,
        headers: dict,
    ) -> dict[str, int]:
        """合并多数据源，构建 app_id -> 总榜排名 映射（Apple 公开前 100 名）。"""
        rank_map: dict[str, int] = {}

        # 优先 iTunes v1 总榜
        v1_ids = self._fetch_overall_v1(country, chart_type, limit, headers) or []
        for index, app_id in enumerate(v1_ids, start=1):
            rank_map.setdefault(app_id, index)

        # top-free 再补充 RSS v2 总榜
        if chart_type == "top-free":
            v2_ids = self._fetch_overall_v2(country, chart_type, limit, headers) or []
            for index, app_id in enumerate(v2_ids, start=1):
                rank_map.setdefault(app_id, index)

        return rank_map

    def _resolve_total_rank(
        self,
        app_id: str,
        overall_map: dict[str, int],
    ) -> int | None:
        """解析总榜排名；未进入 Apple 公开总榜前 100 时返回 None。"""
        return overall_map.get(app_id)

    def fetch_rankings(
        self,
        country: str,
        chart_type: str,
        limit: int | None = None,
    ) -> list[dict] | None:
        """
        拉取游戏榜前 N 名，并补充对应 App 总榜排名。
        接口失败返回 None；成功但无数据返回空列表。
        """
        time.sleep(1)
        headers = {"User-Agent": self.USER_AGENT}
        fetch_limit = min(limit or Config.FETCH_LIMIT, Config.API_MAX_RESULTS)

        game_items = self._fetch_game_chart_v1(
            country, chart_type, fetch_limit, headers
        )
        if game_items is None:
            return None

        time.sleep(1)
        overall_map = self._build_overall_rank_map(
            country, chart_type, fetch_limit, headers
        )

        games: list[dict] = []
        for index, item in enumerate(game_items[: Config.REPORT_LIMIT], start=1):
            total_rank = self._resolve_total_rank(item["app_id"], overall_map)
            games.append(
                {
                    "app_id": item["app_id"],
                    "app_name": item["app_name"],
                    "developer": item["developer"],
                    "category": item["category"],
                    "icon_url": item["icon_url"],
                    "rank": index,
                    "total_rank": total_rank,
                }
            )

        in_top100 = sum(1 for game in games if game["total_rank"] is not None)
        print(f"✅ {country} - {chart_type}: 游戏榜收录 {len(games)} 款")
        print(f"   总榜前100内 {in_top100} 款")
        if len(games) < Config.REPORT_LIMIT:
            print(
                f"⚠️ 游戏榜仅返回 {len(games)} 款（目标 {Config.REPORT_LIMIT} 款）"
            )
        return games

    def run_daily_task(self) -> dict:
        """执行一次完整的每日抓取任务。"""
        success_count = 0
        failed_count = 0
        total_records = 0
        total_tasks = len(Config.COUNTRIES) * len(Config.CHART_TYPES)

        for country in Config.COUNTRIES:
            for chart_type in Config.CHART_TYPES:
                rankings = self.fetch_rankings(country, chart_type)

                if rankings is None:
                    failed_count += 1
                    print(f"❌ {country} - {chart_type}: 抓取失败")
                    continue

                if not rankings:
                    print(f"⚠️ {country} - {chart_type}: 游戏榜无数据")
                    continue

                try:
                    self.db_manager.save_rankings(rankings, country, chart_type)
                except RuntimeError:
                    failed_count += 1
                    print(f"❌ {country} - {chart_type}: 保存失败")
                    continue

                success_count += 1
                total_records += len(rankings)

        return {
            "total_tasks": total_tasks,
            "success_count": success_count,
            "failed_count": failed_count,
            "total_records": total_records,
        }
