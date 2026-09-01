import os
from datetime import datetime
from zoneinfo import ZoneInfo

from src.analyzer import CHART_LABELS
from src.config import Config

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class Reporter:
    """运营日报生成器，输出 Markdown 格式分析报告。"""

    def __init__(self, analyzer):
        """注入数据分析器实例。"""
        self.analyzer = analyzer
        self.reports_dir = "reports"

    def _ensure_reports_dir(self) -> None:
        """确保 reports 目录存在。"""
        os.makedirs(self.reports_dir, exist_ok=True)

    def _format_total_rank(self, total_rank) -> str:
        """格式化总榜排名，未进总榜前 100 或旧数据缺失时显示 '-'。"""
        if total_rank is None:
            return "-"
        return str(total_rank)

    def _build_summary(
        self,
        country: str,
        chart_type: str,
        top_apps: list[dict],
        rising: list[dict],
        new_entries: list[dict],
        has_yesterday: bool,
    ) -> str:
        """根据分析结果自动生成运营小结。"""
        chart_label = CHART_LABELS.get(chart_type, chart_type)
        country_label = "中国" if country == "cn" else country.upper()

        if not has_yesterday:
            return (
                f"今日为 {country_label}{chart_label} 首次游戏榜数据采集，"
                "已记录游戏内排名与总榜排名，明日将提供趋势与异动分析。"
            )

        top1 = top_apps[0]["app_name"] if top_apps else "暂无数据"
        top1_total = self._format_total_rank(
            top_apps[0]["total_rank"] if top_apps else None
        )
        parts = [
            f"今日{country_label}{chart_label}游戏榜由「{top1}」领跑（总榜 #{top1_total}），"
        ]

        if rising:
            best = rising[0]
            parts.append(
                f"「{best['app_name']}」游戏榜上升 {best['rank_change']} 位（"
                f"#{best['yesterday_rank']} → #{best['today_rank']}），值得关注；"
            )
        else:
            parts.append("游戏榜头部格局整体稳定，未见明显排名异动；")

        if new_entries:
            names = "、".join(item["app_name"] for item in new_entries[:3])
            parts.append(f"新入榜游戏包括 {names} 等，建议持续跟踪后续表现。")
        else:
            parts.append(f"今日游戏榜前 {Config.REPORT_LIMIT} 名暂无新面孔进入。")

        return "".join(parts)

    def generate_daily_report(
        self,
        country: str = "cn",
        chart_type: str = "top-free",
        charts: dict[str, str] | None = None,
    ) -> str | None:
        """生成运营日报（Markdown），并保存到 reports/ 目录。"""
        self._ensure_reports_dir()
        today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        chart_label = CHART_LABELS.get(chart_type, chart_type)
        country_label = "中国" if country == "cn" else country.upper()

        if not self.analyzer.has_today_data(country, chart_type):
            message = "今日无数据，请先运行爬虫。"
            print(message)
            return None

        top_apps = self.analyzer.get_today_top(country, chart_type)
        rising = self.analyzer.get_rising_stars(country, chart_type, top_n=5)
        new_entries = self.analyzer.get_new_entries(country, chart_type, top_n=5)
        has_yesterday = self.analyzer.has_yesterday_data(country, chart_type)
        history_days = self.analyzer.get_available_history_days(country, chart_type)

        game_count = len(top_apps)
        if game_count < Config.REPORT_LIMIT:
            section_title = f"## 本期游戏榜共收录 {game_count} 款游戏"
        else:
            section_title = f"## 今日 Top {Config.REPORT_LIMIT}"

        lines: list[str] = [
            f"# 📊 游戏榜单日报 - {today}",
            "",
            f"**市场**：{country_label}　**榜单**：{chart_label}",
            "",
        ]

        if charts and charts.get("trend"):
            lines.extend(
                [
                    f"## 📈 Top {Config.TREND_TOP_N} 排名趋势（近 {min(history_days, Config.TREND_DAYS)} 天）",
                    "",
                    f"![排名趋势]({charts['trend']})",
                    "",
                ]
            )
        elif history_days < 2:
            lines.extend(
                [
                    "## 📈 排名趋势",
                    "",
                    "> 历史数据不足 2 天，趋势图将在后续日报中自动生成。",
                    "",
                ]
            )

        if charts and charts.get("developer"):
            lines.extend(
                [
                    "## 🏢 开发者席位占比",
                    "",
                    f"![开发者占比]({charts['developer']})",
                    "",
                ]
            )

        lines.extend(
            [
                section_title,
                "",
                "| 游戏榜排名 | 总榜排名 | 应用名称 | 开发者 |",
                "| --- | --- | --- | --- |",
            ]
        )

        for item in top_apps:
            total_rank = self._format_total_rank(item.get("total_rank"))
            lines.append(
                f"| {item['rank']} | {total_rank} | "
                f"{item['app_name']} | {item['developer']} |"
            )

        if not top_apps:
            lines.append("| - | - | 暂无数据 | - |")

        lines.extend(["", "## 🔥 上升最快 Top 5", ""])
        if charts and charts.get("rising"):
            lines.extend(
                [
                    f"![上升最快]({charts['rising']})",
                    "",
                ]
            )
        if not has_yesterday:
            lines.append("> 首次运行，明日将提供趋势分析。")
        elif rising:
            lines.extend(
                [
                    "| 应用名称 | 游戏榜变化 | 今日游戏榜排名 |",
                    "| --- | --- | --- |",
                ]
            )
            for item in rising:
                lines.append(
                    f"| {item['app_name']} | ↑{item['rank_change']} "
                    f"(#{item['yesterday_rank']}→#{item['today_rank']}) "
                    f"| #{item['today_rank']} |"
                )
        else:
            lines.append("今日暂无显著上升游戏。")

        lines.extend(["", "## 🆕 新入榜 Top 5", ""])
        if not has_yesterday:
            lines.append("> 首次运行，明日将提供趋势分析。")
        elif new_entries:
            lines.extend(
                [
                    "| 应用名称 | 游戏榜排名 | 总榜排名 | 开发者 |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for item in new_entries:
                total_rank = self._format_total_rank(item.get("total_rank"))
                lines.append(
                    f"| {item['app_name']} | #{item['rank']} | "
                    f"{total_rank} | {item['developer']} |"
                )
        else:
            lines.append(f"今日游戏榜前 {Config.REPORT_LIMIT} 名无新入榜游戏。")

        summary = self._build_summary(
            country, chart_type, top_apps, rising, new_entries, has_yesterday
        )
        lines.extend(["", "## 📝 运营小结", "", summary, ""])

        report_content = "\n".join(lines)
        filename = f"report_{today}_{country}_{chart_type}.md"
        filepath = os.path.join(self.reports_dir, filename)
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(report_content)

        return filepath
