import sys

# Windows 终端默认 GBK，确保 emoji 日志正常输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.analyzer import GameAnalyzer
from src.config import Config
from src.crawler import AppStoreCrawler
from src.database import DatabaseManager
from src.reporter import Reporter


def main() -> None:
    # 初始化数据库与抓取器
    db = DatabaseManager(Config.DATABASE_PATH)
    crawler = AppStoreCrawler(db)

    print("开始执行每日抓取任务...\n")
    summary = crawler.run_daily_task()

    # 打印任务汇总
    print("\n--- 任务汇总 ---")
    print(f"总任务数: {summary['total_tasks']}")
    print(f"成功: {summary['success_count']}")
    print(f"失败: {summary['failed_count']}")
    print(f"写入记录数: {summary['total_records']}")

    apps = db.get_all_apps()
    print(f"当前数据库应用总数: {len(apps)}")

    # 分析与报告生成
    print("\n开始生成运营日报...\n")
    analyzer = GameAnalyzer(db)
    reporter = Reporter(analyzer)

    for country in Config.COUNTRIES:
        for chart_type in Config.CHART_TYPES:
            filepath = reporter.generate_daily_report(
                country=country, chart_type=chart_type
            )
            if filepath:
                print(f"✅ 报告已生成: {filepath}")


if __name__ == "__main__":
    main()
