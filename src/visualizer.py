import os
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.analyzer import CHART_LABELS
from src.config import Config

BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# 跨平台中文字体回退
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


class ChartGenerator:
    """榜单数据可视化，输出 PNG 静态图供 Markdown 报告引用。"""

    def __init__(self, analyzer, output_dir: str | None = None):
        self.analyzer = analyzer
        self.output_dir = output_dir or Config.CHARTS_DIR

    def _ensure_output_dir(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)

    def _chart_basename(self, today: str, country: str, chart_type: str, suffix: str) -> str:
        return f"{today}_{country}_{chart_type}_{suffix}.png"

    def _chart_path(self, today: str, country: str, chart_type: str, suffix: str) -> str:
        filename = self._chart_basename(today, country, chart_type, suffix)
        return os.path.join(self.output_dir, filename)

    def _markdown_path(self, today: str, country: str, chart_type: str, suffix: str) -> str:
        """返回相对于 reports/ 目录的图片引用路径。"""
        charts_subdir = os.path.basename(self.output_dir.rstrip("/\\"))
        filename = self._chart_basename(today, country, chart_type, suffix)
        return f"{charts_subdir}/{filename}"

    def _truncate_label(self, text: str, max_len: int = 12) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def generate_trend_chart(
        self,
        country: str,
        chart_type: str,
        today: str | None = None,
    ) -> str | None:
        """生成 Top N 排名趋势折线图，至少需要 2 天历史数据。"""
        if self.analyzer.get_available_history_days(country, chart_type) < 2:
            return None

        history = self.analyzer.get_top_apps_rank_history(country, chart_type)
        if not history or not history["series"]:
            return None

        chart_label = CHART_LABELS.get(chart_type, chart_type)
        country_label = "中国" if country == "cn" else country.upper()
        dates = history["dates"]
        x_labels = [date[5:] for date in dates]

        fig, ax = plt.subplots(figsize=(12, 6))
        for item in history["series"]:
            y_values = [rank if rank is not None else float("nan") for rank in item["ranks"]]
            ax.plot(
                x_labels,
                y_values,
                marker="o",
                linewidth=2,
                label=self._truncate_label(item["app_name"], 10),
            )

        ax.invert_yaxis()
        ax.set_xlabel("日期 (月-日)")
        ax.set_ylabel("游戏榜排名")
        ax.set_title(
            f"{country_label}{chart_label} Top {Config.TREND_TOP_N} 排名趋势（近 {len(dates)} 天）"
        )
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=9)
        fig.tight_layout()

        report_date = today or datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        self._ensure_output_dir()
        filepath = self._chart_path(report_date, country, chart_type, "trend")
        fig.savefig(filepath, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return self._markdown_path(report_date, country, chart_type, "trend")

    def generate_rising_chart(
        self,
        country: str,
        chart_type: str,
        rising: list[dict],
        today: str | None = None,
    ) -> str | None:
        """生成上升最快柱状图。"""
        if not rising:
            return None

        chart_label = CHART_LABELS.get(chart_type, chart_type)
        country_label = "中国" if country == "cn" else country.upper()
        names = [self._truncate_label(item["app_name"], 14) for item in rising]
        changes = [item["rank_change"] for item in rising]

        fig, ax = plt.subplots(figsize=(10, max(4, len(rising) * 0.8)))
        bars = ax.barh(names, changes, color="#e74c3c")
        ax.invert_yaxis()
        ax.set_xlabel("上升位数")
        ax.set_title(f"{country_label}{chart_label} 上升最快 Top {len(rising)}")
        ax.bar_label(bars, fmt="+%d", padding=3)

        report_date = today or datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        self._ensure_output_dir()
        filepath = self._chart_path(report_date, country, chart_type, "rising")
        fig.tight_layout()
        fig.savefig(filepath, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return self._markdown_path(report_date, country, chart_type, "rising")

    def generate_developer_chart(
        self,
        country: str,
        chart_type: str,
        today: str | None = None,
    ) -> str | None:
        """生成 Top 50 开发者席位占比饼图。"""
        share = self.analyzer.get_developer_share(country, chart_type)
        if not share:
            return None

        chart_label = CHART_LABELS.get(chart_type, chart_type)
        country_label = "中国" if country == "cn" else country.upper()
        labels = [self._truncate_label(item["developer"], 16) for item in share]
        sizes = [item["count"] for item in share]

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.pie(
            sizes,
            labels=labels,
            autopct="%1.0f%%",
            startangle=140,
            textprops={"fontsize": 9},
        )
        ax.set_title(
            f"{country_label}{chart_label} Top {Config.REPORT_LIMIT} 开发者席位占比"
        )

        report_date = today or datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        self._ensure_output_dir()
        filepath = self._chart_path(report_date, country, chart_type, "developer")
        fig.tight_layout()
        fig.savefig(filepath, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return self._markdown_path(report_date, country, chart_type, "developer")

    def generate_all(
        self,
        country: str,
        chart_type: str,
        rising: list[dict] | None = None,
        today: str | None = None,
    ) -> dict[str, str]:
        """生成全部图表，返回 {类型: Markdown 相对路径}。"""
        report_date = today or self.analyzer.get_today_date()
        charts: dict[str, str] = {}

        trend_path = self.generate_trend_chart(country, chart_type, report_date)
        if trend_path:
            charts["trend"] = trend_path

        rising_data = rising if rising is not None else self.analyzer.get_rising_stars(
            country, chart_type, top_n=5
        )
        rising_path = self.generate_rising_chart(
            country, chart_type, rising_data, report_date
        )
        if rising_path:
            charts["rising"] = rising_path

        developer_path = self.generate_developer_chart(country, chart_type, report_date)
        if developer_path:
            charts["developer"] = developer_path

        return charts
