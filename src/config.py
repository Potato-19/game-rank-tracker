class Config:
    """项目全局配置。"""

    COUNTRIES = ['cn', 'us']
    CHART_TYPES = ['top-free', 'top-grossing']
    FETCH_LIMIT = 200   # 扫描目标深度（Apple RSS 单次实际最多返回 100 条）
    REPORT_LIMIT = 50   # 最终报告展示 50 款游戏
    API_MAX_RESULTS = 100  # App Store RSS 接口单次上限
    # 游戏类应用分类标识（中/英文及 genreId）
    GAME_CATEGORIES = {'Games', '游戏', '6014'}
    # 相对路径，本地与 GitHub Actions 环境均可正常使用
    DATABASE_PATH = 'data/game_ranks.db'
