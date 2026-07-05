"""
Tests for Recommendation System (Board Scanner + Fund Screener + Recommendation Engine)
TDD: 测试核心逻辑的纯函数部分 (不依赖网络API)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_board_scanner_continuity():
    """测试板块K线连续性分析"""
    from engine.board_scanner import BoardScanner

    scanner = BoardScanner()

    # 模拟连涨5天的K线数据
    klines = [
        {"date": "2024-01-10", "close": 100, "change_pct": 1.0},
        {"date": "2024-01-11", "close": 101, "change_pct": 1.5},
        {"date": "2024-01-12", "close": 102.5, "change_pct": 2.0},
        {"date": "2024-01-13", "close": 103, "change_pct": 0.5},
        {"date": "2024-01-14", "close": 104.5, "change_pct": 1.5},
    ]

    result = scanner.analyze_continuity(klines)
    assert result["consecutive_up"] == 5, f"Expected 5 consecutive up, got {result['consecutive_up']}"
    assert result["consecutive_down"] == 0
    assert result["avg_change_5d"] > 0  # 近5日均值应为正
    print("✅ test_board_scanner_continuity PASSED")


def test_board_scanner_continuity_mixed():
    """测试混合涨跌的K线"""
    from engine.board_scanner import BoardScanner

    scanner = BoardScanner()
    klines = [
        {"date": "2024-01-10", "change_pct": -1.0},
        {"date": "2024-01-11", "change_pct": 2.0},
        {"date": "2024-01-12", "change_pct": -0.5},
        {"date": "2024-01-13", "change_pct": 1.5},
        {"date": "2024-01-14", "change_pct": -2.0},
    ]

    result = scanner.analyze_continuity(klines)
    assert result["consecutive_up"] == 0, "最后一天是跌的"
    assert result["consecutive_down"] == 1, "最后一天跌"
    print("✅ test_board_scanner_continuity_mixed PASSED")


def test_fund_screener_c_identification():
    """测试C类基金识别"""
    from engine.fund_screener import FundScreener

    screener = FundScreener()
    fund_list = [
        {"code": "001234", "name": "天弘半导体C"},
        {"code": "001235", "name": "天弘半导体A"},
        {"code": "001236", "name": "华夏芯片指数C"},
        {"code": "001237", "name": "富国消费电子C类"},
        {"code": "001238", "name": "货币基金C"},
        {"code": "001239", "name": "广发军工混合C"},
    ]

    c_funds = screener.find_c_funds_by_board("半导体", fund_list)
    codes = [f["code"] for f in c_funds]

    assert "001234" in codes, "天弘半导体C应被选中"
    assert "001235" not in codes, "A类不应被选中"
    assert "001236" in codes, "华夏芯片指数C应被选中"
    assert "001237" not in codes, "货币基金应被排除"
    assert "001239" not in codes, "军工不在半导体关键词中"
    print("✅ test_fund_screener_c_identification PASSED")


def test_fund_screener_multi_board_match():
    """测试多板块关键词匹配"""
    from engine.fund_screener import FundScreener

    screener = FundScreener()
    fund_list = [
        {"code": "003001", "name": "易方达人工智能C"},
        {"code": "003002", "name": "嘉实AIGC主题C"},
        {"code": "003003", "name": "南方消费电子C"},
    ]

    # "AI算力" 关键词: ["算力", "AI", "人工智能", "数字经济"]
    c_funds = screener.find_c_funds_by_board("AI算力", fund_list)
    codes = [f["code"] for f in c_funds]
    assert "003001" in codes, "人工智能应匹配AI算力"
    assert "003002" in codes, "AIGC应匹配AI算力"
    assert "003003" not in codes, "消费电子不匹配AI算力"

    # "消费电子" 关键词
    c_funds2 = screener.find_c_funds_by_board("消费电子", fund_list)
    codes2 = [f["code"] for f in c_funds2]
    assert "003003" in codes2, "消费电子应匹配"
    assert "003001" not in codes2, "人工智能不匹配消费电子"
    print("✅ test_fund_screener_multi_board_match PASSED")


def test_win_rate_calculation():
    """测试滚动窗口胜率计算"""
    from engine.fund_screener import FundScreener

    screener = FundScreener()

    # 构造120天净值数据: 前60天上涨, 后60天下跌
    nav_data = []
    price = 1.0
    for i in range(120):
        if i < 60:
            price *= 1.003  # 每天涨0.3%
        else:
            price *= 0.997  # 每天跌0.3%
        nav_data.append({
            "date": f"2024-{i//30+1:02d}-{i%30+1:02d}",
            "nav": round(price, 4),
            "daily_change_pct": 0.3 if i < 60 else -0.3,
        })

    result = screener.analyze_fund_history(nav_data)

    # 7天胜率: 在上涨期应该很高，在下跌期应该很低
    # 整体混合，胜率应该在40-60%之间
    wr7 = result["win_rate_7d"]["win_rate"]
    assert 30 < wr7 < 80, f"7天胜率应在30-80%之间, 实际{wr7}%"
    assert result["win_rate_7d"]["samples"] > 0, "应有样本"
    assert result["max_drawdown_pct"] > 0, "应有回撤"

    print(f"✅ test_win_rate_calculation PASSED (7天胜率={wr7}%, "
          f"最大回撤={result['max_drawdown_pct']}%)")


def test_win_rate_pure_uptrend():
    """测试纯上涨趋势的胜率"""
    from engine.fund_screener import FundScreener

    screener = FundScreener()

    nav_data = []
    price = 1.0
    for i in range(120):
        price *= 1.005  # 每天涨0.5%
        nav_data.append({
            "date": f"2024-{i//30+1:02d}-{i%30+1:02d}",
            "nav": round(price, 4),
            "daily_change_pct": 0.5,
        })

    result = screener.analyze_fund_history(nav_data)

    wr7 = result["win_rate_7d"]["win_rate"]
    wr14 = result["win_rate_14d"]["win_rate"]
    wr30 = result["win_rate_30d"]["win_rate"]

    assert wr7 == 100, f"纯上涨7天胜率应为100%, 实际{wr7}%"
    assert wr14 == 100, f"纯上涨14天胜率应为100%, 实际{wr14}%"
    assert wr30 == 100, f"纯上涨30天胜率应为100%, 实际{wr30}%"
    assert result["max_drawdown_pct"] == 0, "纯上涨不应有回撤"
    assert result["annual_return_pct"] > 0, "年化收益应为正"

    print(f"✅ test_win_rate_pure_uptrend PASSED (7天={wr7}%, 14天={wr14}%, 30天={wr30}%)")


def test_report_formatter():
    """测试报告格式化器"""
    from advisor.report_formatter import ReportFormatter

    # 构造最小报告
    report = {
        "report_time": "2024-01-15 14:30",
        "summary": {
            "total_boards_scanned": 5,
            "total_funds_screened": 23,
            "total_qualified": 3,
            "min_win_rate_filter": "7天>=50% & 14天>=50%",
            "avg_wr7_top": 58.3,
            "avg_wr14_top": 55.1,
            "avg_annual_return_top": 12.5,
        },
        "hot_boards": [
            {
                "name": "半导体",
                "change_pct": 2.35,
                "score": 78.5,
                "main_flow_pct": 1.23,
                "funds_found": 8,
                "funds_qualified": 3,
            }
        ],
        "recommendations": [
            {
                "rank": 1,
                "fund_code": "001234",
                "fund_name": "天弘半导体C",
                "board_name": "半导体",
                "total_score": 72.5,
                "win_rate_7d": {"win_rate": 58.0, "avg_return": 0.85, "median_return": 0.92, "samples": 300},
                "win_rate_14d": {"win_rate": 55.0, "avg_return": 1.20, "median_return": 1.05, "samples": 280},
                "win_rate_30d": {"win_rate": 52.0, "avg_return": 2.10, "median_return": 1.80, "samples": 250},
                "annual_return_pct": 15.3,
                "max_drawdown_pct": 12.5,
                "sharpe_ratio": 1.23,
                "annual_volatility_pct": 18.5,
                "recent_20d_pct": 3.2,
                "data_days": 365,
                "latest_nav": 1.2345,
                "board_change_pct": 2.35,
                "board_score": 78.5,
                "board_main_flow_pct": 1.23,
                "board_consecutive_up": 3,
                "board_avg_5d": 1.8,
                "fee_lock_days": 7,
                "fee_first_7d": "1.5%惩罚费",
                "reasons": [
                    "板块热度: [半导体] 今日上涨 2.35%，主力资金净流入占比 1.23%",
                    "7天持有胜率: 58.0% (统计300个窗口, 平均收益 0.85%, 中位数收益 0.92%)",
                ],
                "risks": [
                    "C类基金: 持有不足7天赎回将收取1.5%惩罚费",
                    "历史最大回撤 12.5%，波动较大",
                ],
            }
        ],
    }

    # 测试终端格式化
    terminal = ReportFormatter.format_terminal(report)
    assert "001234" in terminal
    assert "58.0%" in terminal
    assert "2.35%" in terminal
    assert "推荐理由" in terminal
    assert "风险提示" in terminal

    # 测试Markdown格式化
    md = ReportFormatter.format_markdown(report)
    assert "## 推荐基金" in md
    assert "**7天胜率**" in md

    print("✅ test_report_formatter PASSED")


def test_error_report():
    """测试错误报告格式化"""
    from advisor.report_formatter import ReportFormatter

    report = {"error": "板块扫描失败"}
    terminal = ReportFormatter.format_terminal(report)
    assert "错误" in terminal
    md = ReportFormatter.format_markdown(report)
    assert "错误" in md

    print("✅ test_error_report PASSED")


if __name__ == "__main__":
    test_board_scanner_continuity()
    test_board_scanner_continuity_mixed()
    test_fund_screener_c_identification()
    test_fund_screener_multi_board_match()
    test_win_rate_calculation()
    test_win_rate_pure_uptrend()
    test_report_formatter()
    test_error_report()
    print("\n🎉 All recommendation tests passed!")
