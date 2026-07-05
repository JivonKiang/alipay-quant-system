"""
Report Formatter — 推荐报告格式化器
将推荐引擎的JSON输出格式化为人类可读的报告
支持: 终端文本 / Markdown / JSON
"""
import json
from datetime import datetime
from typing import Dict, List


class ReportFormatter:
    """报告格式化器"""

    @staticmethod
    def format_terminal(report: Dict) -> str:
        """格式化为终端文本输出"""
        if "error" in report:
            return f"❌ 推荐引擎错误: {report['error']}"

        lines = []
        lines.append("=" * 70)
        lines.append(f"📊 基金推荐报告 — {report['report_time']}")
        lines.append("=" * 70)

        # 汇总
        s = report["summary"]
        lines.append(f"\n📋 扫描汇总:")
        lines.append(f"   扫描板块: {s['total_boards_scanned']} 个")
        lines.append(f"   筛选基金: {s['total_funds_screened']} 只")
        lines.append(f"   达标基金: {s['total_qualified']} 只")
        lines.append(f"   过滤条件: {s['min_win_rate_filter']}")
        if "avg_wr7_top" in s:
            lines.append(f"   Top推荐平均: 7天胜率{s['avg_wr7_top']}%, "
                         f"14天胜率{s['avg_wr14_top']}%, "
                         f"年化{s['avg_annual_return_top']}%")

        # 热门板块
        lines.append(f"\n🔥 热门板块:")
        for i, b in enumerate(report.get("hot_boards", [])):
            marker = "🟢" if b["change_pct"] > 0 else "🔴"
            lines.append(
                f"   {marker} {i+1}. [{b['name']}] "
                f"涨幅 {b['change_pct']:+.2f}% | "
                f"主力流入 {b['main_flow_pct']:+.2f}% | "
                f"综合分 {b['score']:.1f} | "
                f"基金 {b['funds_qualified']}/{b['funds_found']}达标"
            )

        # 推荐详情
        recs = report.get("recommendations", [])
        if not recs:
            lines.append(f"\n⚠️ 当前无达标基金推荐 (所有基金胜率未达过滤阈值)")

        for rec in recs:
            lines.append(f"\n{'─' * 70}")
            lines.append(
                f"🥇 #{rec['rank']} | {rec['fund_code']} {rec['fund_name']}"
            )
            lines.append(
                f"   板块: [{rec['board_name']}] "
                f"(今日{rec['board_change_pct']:+.2f}%) | "
                f"综合评分: {rec['total_score']:.1f}"
            )

            # 核心数据卡片
            lines.append(f"\n   📊 核心数据 (基于{rec['data_days']}天历史数据):")
            lines.append(
                f"   ┌─ 7天持有胜率:  {rec['win_rate_7d']['win_rate']}%  "
                f"(均值{rec['win_rate_7d']['avg_return']:+.2f}%, "
                f"中位数{rec['win_rate_7d']['median_return']:+.2f}%)"
            )
            lines.append(
                f"   ├─ 14天持有胜率: {rec['win_rate_14d']['win_rate']}%  "
                f"(均值{rec['win_rate_14d']['avg_return']:+.2f}%)"
            )
            lines.append(
                f"   ├─ 30天持有胜率: {rec['win_rate_30d']['win_rate']}%  "
                f"(均值{rec['win_rate_30d']['avg_return']:+.2f}%)"
            )
            lines.append(
                f"   ├─ 年化收益: {rec['annual_return_pct']}%  |  "
                f"最大回撤: {rec['max_drawdown_pct']}%  |  "
                f"夏普: {rec['sharpe_ratio']}"
            )
            lines.append(
                f"   └─ 年化波动: {rec['annual_volatility_pct']}%  |  "
                f"近20日: {rec['recent_20d_pct']:+.2f}%  |  "
                f"最新净值: {rec['latest_nav']}"
            )

            # 推荐理由
            lines.append(f"\n   ✅ 推荐理由:")
            for reason in rec.get("reasons", []):
                lines.append(f"   • {reason}")

            # 风险提示
            lines.append(f"\n   ⚠️ 风险提示:")
            for risk in rec.get("risks", []):
                lines.append(f"   • {risk}")

            # C类费率提醒
            lines.append(f"\n   💰 C类费率: 锁定{rec['fee_lock_days']}天, "
                         f"{rec['fee_first_7d']}")

        lines.append(f"\n{'=' * 70}")
        lines.append(f"📝 以上推荐基于历史数据回测，不构成投资建议。")
        lines.append(f"   历史胜率不代表未来收益，请根据自身风险承受能力决策。")
        lines.append(f"   建议至少持有7天以上以避免C类惩罚费。")
        lines.append(f"{'=' * 70}")

        return "\n".join(lines)

    @staticmethod
    def format_markdown(report: Dict) -> str:
        """格式化为Markdown"""
        if "error" in report:
            return f"**错误**: {report['error']}"

        lines = []
        lines.append(f"# 基金推荐报告 — {report['report_time']}")
        lines.append("")

        # 汇总
        s = report["summary"]
        lines.append("## 扫描汇总")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 扫描板块数 | {s['total_boards_scanned']} |")
        lines.append(f"| 筛选基金数 | {s['total_funds_screened']} |")
        lines.append(f"| 达标基金数 | {s['total_qualified']} |")
        lines.append(f"| 过滤条件 | {s['min_win_rate_filter']} |")
        if "avg_wr7_top" in s:
            lines.append(f"| Top平均7天胜率 | {s['avg_wr7_top']}% |")
            lines.append(f"| Top平均14天胜率 | {s['avg_wr14_top']}% |")
            lines.append(f"| Top平均年化 | {s['avg_annual_return_top']}% |")
        lines.append("")

        # 热门板块
        lines.append("## 热门板块")
        lines.append("| # | 板块 | 今日涨幅 | 主力流入% | 综合分 | 基金达标 |")
        lines.append("|---|------|---------|----------|--------|---------|")
        for i, b in enumerate(report.get("hot_boards", [])):
            lines.append(
                f"| {i+1} | {b['name']} | {b['change_pct']:+.2f}% | "
                f"{b['main_flow_pct']:+.2f}% | {b['score']:.1f} | "
                f"{b['funds_qualified']}/{b['funds_found']} |"
            )
        lines.append("")

        # 推荐详情
        lines.append("## 推荐基金")
        for rec in report.get("recommendations", []):
            lines.append(f"### #{rec['rank']} {rec['fund_code']} {rec['fund_name']}")
            lines.append(f"- **板块**: {rec['board_name']} (今日 {rec['board_change_pct']:+.2f}%)")
            lines.append(f"- **综合评分**: {rec['total_score']:.1f}")
            lines.append(f"- **7天胜率**: {rec['win_rate_7d']['win_rate']}% (均值 {rec['win_rate_7d']['avg_return']:+.2f}%, 中位数 {rec['win_rate_7d']['median_return']:+.2f}%)")
            lines.append(f"- **14天胜率**: {rec['win_rate_14d']['win_rate']}% (均值 {rec['win_rate_14d']['avg_return']:+.2f}%)")
            lines.append(f"- **30天胜率**: {rec['win_rate_30d']['win_rate']}% (均值 {rec['win_rate_30d']['avg_return']:+.2f}%)")
            lines.append(f"- **年化收益**: {rec['annual_return_pct']}% | **最大回撤**: {rec['max_drawdown_pct']}% | **夏普**: {rec['sharpe_ratio']}")
            lines.append(f"- **波动率**: {rec['annual_volatility_pct']}% | **近20日**: {rec['recent_20d_pct']:+.2f}%")
            lines.append(f"- **C类锁定**: {rec['fee_lock_days']}天")
            lines.append("")
            lines.append("**推荐理由:**")
            for r in rec.get("reasons", []):
                lines.append(f"- {r}")
            lines.append("")
            lines.append("**风险提示:**")
            for r in rec.get("risks", []):
                lines.append(f"- {r}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def save_json(report: Dict, filepath: str):
        """保存为JSON文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
