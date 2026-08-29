# 🎮 App Store 游戏榜单自动追踪工具

> 一个面向游戏运营的竞品数据监控工具，每日自动抓取App Store榜单数据并生成运营日报。

## ✨ 核心功能

- 📊 **数据抓取**：每日自动获取中美两国免费榜、畅销榜Top 50
- 💾 **历史存储**：SQLite数据库保存每日排名快照，支持趋势分析
- 🔍 **智能分析**：自动识别排名飙升、新入榜应用等运营信号
- 📝 **日报生成**：产出Markdown格式运营报告，可直接用于周报
- ⏰ **全自动运行**：通过GitHub Actions实现每日定时执行

## 🛠️ 技术栈

- Python 3.10+
- Requests（数据抓取）
- SQLite（数据存储）
- Pandas（数据分析）
- GitHub Actions（自动化调度）

## 📁 项目结构
game-rank-tracker/
├── src/
│ ├── config.py # 配置文件（国家、榜单类型等）
│ ├── database.py # 数据库操作
│ ├── crawler.py # 榜单数据抓取
│ ├── analyzer.py # 数据分析
│ └── reporter.py # 报告生成
├── data/
│ └── game_ranks.db # SQLite数据库
├── reports/ # 自动生成的日报
├── main.py # 程序入口
└── .github/workflows/ # GitHub Actions自动化配置

## 📊 报告示例

报告文件位于 `reports/` 文件夹，内容包含：
- 今日Top 10榜单
- 排名上升最快Top 5
- 新入榜应用
- 运营小结

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 手动执行
python main.py

# 3. 自动执行：代码推送后，GitHub Actions会在每天上午9点自动运行
📅 数据来源
App Store官方RSS接口

国家：中国（cn）、美国（us）

榜单：免费榜（top-free）、畅销榜（top-grossing）