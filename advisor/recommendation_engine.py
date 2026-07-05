"""
Recommendation Engine — 推荐引擎
完整决策链: 热门板块扫描 → C类基金筛选 → 历史胜率回测 → 生成推荐报告
"""
import json
import time
from datetime import datetime
from typing import List, Dict

from engine.board_scanner import BoardScanner
from engine.fund_screener import FundScreener
from risk.fee_manager import FeeManager


class RecommendationEngine:
    """
    推荐引擎
    流程:
      1. 扫描全部概念板块，多因子打分取Top N
      2. 对每个热门板块，筛选对应的C类基金
      3. 获取基金历史净值，计算7天/14天/30天持有胜率
      4. 综合评分排名，生成结构化推荐报告
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.scanner = BoardScanner(config.get("scanner", {}))
        self.screener = FundScreener(config.get("screener", {}))
        self.fee_mgr = FeeManager(config.get("fee", {}))
        self.top_boards = config.get("top_boards", 5)
        self.top_funds_per_board = config.get("top_funds_per_board", 3)
        self.min_win_rate_7d = config.get("min_win_rate_7d", 50)
        self.min_win_rate_14d = config.get("min_win_rate_14d", 50)

    def run(self, board_type: str = "concept") -> Dict:
        """
        执行完整推荐流程
        返回结构化推荐报告
        """
        report_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        print(f"\n{'='*60}")
        print(f"📊 推荐引擎启动 — {report_time}")
        print(f"{'='*60}")

        # ===== Step 1: 扫描热门板块 =====
        print(f"\n📌 Step 1/3: 扫描热门板块 (Top {self.top_boards})")
        top_boards = self.scanner.scan(top_n=self.top_boards, board_type=board_type)

        if not top_boards:
            return {
                "error": "板块扫描失败，无法获取市场数据",
                "report_time": report_time,
            }

        # ===== Step 2: 对每个板块筛选基金 =====
        print(f"\n📌 Step 2/3: 筛选各板块C类基金 (每板块 Top {self.top_funds_per_board})")
        fund_list = self.screener.fetch_fund_list()
        print(f"   已加载全量基金列表: {len(fund_list)} 只")

        board_fund_results = []
        for board in top_boards:
            board_name = board["name"]
            screened = self.screener.screen(
                board_name,
                top_n=self.top_funds_per_board,
                fund_list=fund_list,
            )

            # 过滤: 7天和14天胜率都需达标
            qualified = []
            for f in screened:
                a = f["analysis"]
                wr7 = a["win_rate_7d"]["win_rate"]
                wr14 = a["win_rate_14d"]["win_rate"]
                if wr7 >= self.min_win_rate_7d and wr14 >= self.min_win_rate_14d:
                    qualified.append(f)

            board_fund_results.append({
                "board": board,
                "all_funds": screened,
                "qualified_funds": qualified,
            })
            time.sleep(0.5)

        # ===== Step 3: 生成推荐报告 =====
        print(f"\n📌 Step 3/3: 生成推荐报告")
        report = self._build_report(board_fund_results, report_time)
        return report

    def _build_report(self, board_fund_results: List[Dict], report_time: str) -> Dict:
        """构建结构化推荐报告"""

        # ---- 收集所有达标基金，全局排名 ----
        all_qualified = []
        for bfr in board_fund_results:
            board_info = bfr["board"]
            for f in bfr["qualified_funds"]:
                all_qualified.append({
                    "fund": f,
                    "board_name": board_info["name"],
                    "board_change_pct": board_info["change_pct"],
                    "board_score": board_info["scores"]["total"],
                    "board_main_flow_pct": board_info["main_flow_pct"],
                    "board_kline": board_info["kline_analysis"],
                })

        # 按基金总分排名
        all_qualified.sort(key=lambda x: x["fund"]["scores"]["total"], reverse=True)

        # ---- 推荐列表 (带充分理由) ----
        recommendations = []
        for item in all_qualified[:10]:
            f = item["fund"]
            a = f["analysis"]
            s = f["scores"]
            board_name = item["board_name"]

            # 生成推荐理由 (充分、有数据支撑)
            reasons = self._generate_reasons(item)
            # 风险提示
            risks = self._generate_risks(item)

            # 费率信息
            fee_info = self.fee_mgr.get_fee_tier(0, f["code"])

            recommendations.append({
                "rank": len(recommendations) + 1,
                "fund_code": f["code"],
                "fund_name": f["name"],
                "board_name": board_name,
                "matched_keyword": f.get("matched_keyword", ""),
                "total_score": s["total"],
                # 关键数据
                "win_rate_7d": a["win_rate_7d"],
                "win_rate_14d": a["win_rate_14d"],
                "win_rate_30d": a["win_rate_30d"],
                "annual_return_pct": a["annual_return_pct"],
                "max_drawdown_pct": a["max_drawdown_pct"],
                "sharpe_ratio": a["sharpe_ratio"],
                "annual_volatility_pct": a["annual_volatility_pct"],
                "recent_20d_pct": a["recent_20d_pct"],
                "data_days": a["data_days"],
                "latest_nav": a["latest_nav"],
                # 板块数据
                "board_change_pct": item["board_change_pct"],
                "board_score": item["board_score"],
                "board_main_flow_pct": item["board_main_flow_pct"],
                "board_consecutive_up": item["board_kline"].get("consecutive_up", 0),
                "board_avg_5d": item["board_kline"].get("avg_change_5d", 0),
                # 费率
                "fee_lock_days": fee_info["lock_days"],
                "fee_first_7d": "1.5%惩罚费",
                # 理由和风险
                "reasons": reasons,
                "risks": risks,
            })

        # ---- 汇总统计 ----
        summary = {
            "total_boards_scanned": sum(1 for _ in board_fund_results),
            "total_funds_screened": sum(len(bfr["all_funds"]) for bfr in board_fund_results),
            "total_qualified": len(all_qualified),
            "min_win_rate_filter": f"7天≥{self.min_win_rate_7d}% & 14天≥{self.min_win_rate_14d}%",
        }

        if all_qualified:
            avg_wr7 = sum(r["win_rate_7d"]["win_rate"] for r in recommendations) / len(recommendations)
            avg_wr14 = sum(r["win_rate_14d"]["win_rate"] for r in recommendations) / len(recommendations)
            avg_return = sum(r["annual_return_pct"] for r in recommendations) / len(recommendations)
            summary.update({
                "avg_wr7_top": round(avg_wr7, 1),
                "avg_wr14_top": round(avg_wr14, 1),
                "avg_annual_return_top": round(avg_return, 1),
            })

        return {
            "report_time": report_time,
            "summary": summary,
            "hot_boards": [
                {
                    "name": bfr["board"]["name"],
                    "change_pct": bfr["board"]["change_pct"],
                    "score": bfr["board"]["scores"]["total"],
                    "main_flow_pct": bfr["board"]["main_flow_pct"],
                    "funds_found": len(bfr["all_funds"]),
                    "funds_qualified": len(bfr["qualified_funds"]),
                }
                for bfr in board_fund_results
            ],
            "recommendations": recommendations,
        }

    def _generate_reasons(self, item: Dict) -> List[str]:
        """生成充分的推荐理由 (每条都有数据支撑)"""
        f = item["fund"]
        a = f["analysis"]
        s = f["scores"]
        board_name = item["board_name"]

        reasons = []

        # 1. 板块热度
        chg = item["board_change_pct"]
        if chg > 0:
            reasons.append(
                f"板块热度: [{board_name}] 今日上涨 {chg:.2f}%，"
                f"主力资金净流入占比 {item['board_main_flow_pct']:.2f}%"
            )
        consec = item["board_consecutive_up"]
        if consec >= 2:
            reasons.append(
                f"板块趋势: [{board_name}] 连续 {consec} 天上涨，"
                f"近5日平均涨幅 {item['board_avg_5d']:.2f}%"
            )

        # 2. 持有胜率 (核心)
        wr7 = a["win_rate_7d"]
        reasons.append(
            f"7天持有胜率: {wr7['win_rate']}% "
            f"(统计 {wr7['samples']} 个窗口，"
            f"平均收益 {wr7['avg_return']:.2f}%，"
            f"中位数收益 {wr7['median_return']:.2f}%)"
        )
        wr14 = a["win_rate_14d"]
        reasons.append(
            f"14天持有胜率: {wr14['win_rate']}% "
            f"(统计 {wr14['samples']} 个窗口，"
            f"平均收益 {wr14['avg_return']:.2f}%)"
        )

        # 3. 收益风险比
        if a["max_drawdown_pct"] > 0:
            ratio = a["annual_return_pct"] / a["max_drawdown_pct"]
            reasons.append(
                f"收益回撤比: 年化 {a['annual_return_pct']}% / "
                f"最大回撤 {a['max_drawdown_pct']}% = {ratio:.2f}"
            )
        reasons.append(
            f"夏普比率: {a['sharpe_ratio']} "
            f"(年化波动 {a['annual_volatility_pct']}%)"
        )

        # 4. 近期趋势
        r20d = a["recent_20d_pct"]
        if r20d > 0:
            reasons.append(f"近20日收益: +{r20d}%，短期趋势向上")
        elif r20d < -3:
            reasons.append(f"近20日收益: {r20d}%，短期有回调")
        else:
            reasons.append(f"近20日收益: {r20d}%，短期震荡")

        return reasons

    def _generate_risks(self, item: Dict) -> List[str]:
        """生成风险提示"""
        f = item["fund"]
        a = f["analysis"]
        risks = []

        # 1. 持有期费率风险
        risks.append(f"C类基金: 持有不足7天赎回将收取1.5%惩罚费，建议至少持有7天")

        # 2. 回撤风险
        if a["max_drawdown_pct"] > 15:
            risks.append(f"历史最大回撤 {a['max_drawdown_pct']}%，波动较大，注意仓位控制")

        # 3. 胜率不保证
        wr7 = a["win_rate_7d"]["win_rate"]
        if wr7 < 60:
            risks.append(f"7天胜率 {wr7}%，并非确定性机会，建议小仓位试错")

        # 4. 趋势逆转
        if item["board_consecutive_up"] >= 4:
            risks.append(
                f"板块已连涨 {item['board_consecutive_up']} 天，"
                f"存在短期回调压力"
            )

        # 5. 波动率风险
        if a["annual_volatility_pct"] > 25:
            risks.append(f"年化波动率 {a['annual_volatility_pct']}%，属于高波动品种")

        return risks


from typing import Dict
