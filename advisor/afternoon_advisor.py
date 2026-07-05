"""
Afternoon Advisor v2 — 14:30 场内研判引擎
参考: Jesse (零偏差回测) + Freqtrade (ML信号) + Qlib (AI因子)

核心改进:
1. 科学决策: 基于基金估算净值(非板块) + 波动率z-score(非固定阈值)
2. Hybrid时机: 止盈止损2:30立即判, 买入留到收盘后
3. 费率感知: C类7天/30天分层, 所有操作都计算净收益
4. 多策略信号: MA/动量/板块轮动多维度交叉验证
"""
import json
import math
import os
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple

from engine.data_fetcher import DataFetcher
from risk.fee_manager import FeeManager
from risk.position_sizer import PositionSizer


class AfternoonAdvisor:
    """14:30 场内研判引擎"""

    def __init__(self, config_path: str = "config.yaml"):
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.data_fetcher = DataFetcher()
        self.fee_manager = FeeManager(self.config.get("fee", {}))
        self.position_sizer = PositionSizer(self.config.get("capital", {}))
        self.risk_config = self.config.get("risk", {})
        self.boards = self.config.get("boards", {})
        self.indexes = self.config.get("indexes", {})

        # 路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.positions_file = os.path.join(script_dir, "..", "positions.json")
        self.output_dir = os.path.join(script_dir, "..", "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def assess_market_environment(self) -> Dict:
        """评估市场环境 (五大指数)"""
        indices = self.data_fetcher.fetch_index_snapshot()
        bullish = sum(1 for v in indices.values() if v.get("change_pct", 0) > 0.5)
        bearish = sum(1 for v in indices.values() if v.get("change_pct", 0) < -0.5)

        env_map = [
            (lambda: bullish >= 4, "bull", "强多", 0.75),
            (lambda: bullish >= 3, "bull_lean", "偏多", 0.60),
            (lambda: bearish >= 4, "bear", "强空", 0.20),
            (lambda: bearish >= 3, "bear_lean", "偏熊", 0.35),
        ]

        for condition, env, label, cap in env_map:
            if condition():
                return {"environment": env, "label": label, "position_cap": cap,
                        "bullish": bullish, "bearish": bearish, "indices": indices}

        return {"environment": "range", "label": "震荡", "position_cap": 0.45,
                "bullish": bullish, "bearish": bearish, "indices": indices}

    def analyze_fund(self, fund_code: str, entry_nav: float, entry_amount: float,
                     entry_date: str, board_name: str) -> Dict:
        """单只基金的完整分析"""
        # 1. 获取实时估值
        est = self.data_fetcher.fetch_fund_estimate(fund_code)

        # 2. 获取历史数据 (计算波动率)
        nav_history = self.data_fetcher.fetch_fund_nav(fund_code, 60)

        # 3. 计算盈亏
        current_nav = est["nav_estimate"] if est else entry_nav
        shares = entry_amount / entry_nav if entry_nav > 0 else 0
        current_value = shares * current_nav
        profit = current_value - entry_amount
        profit_pct = (profit / entry_amount * 100) if entry_amount > 0 else 0
        intraday_pct = est["change_pct"] if est else 0

        # 4. 计算持有天数和费率
        days_held = self.fee_manager.days_held(entry_date) if entry_date else 0
        fee = self.fee_manager.get_fee_tier(days_held, fund_code)

        # 5. 计算波动率z-score
        zscore = 0
        if len(nav_history) >= 20:
            daily_changes = []
            for i in range(1, len(nav_history)):
                prev = nav_history[i - 1]["nav"]
                curr = nav_history[i]["nav"]
                if prev > 0:
                    daily_changes.append((curr - prev) / prev * 100)

            if len(daily_changes) >= 20:
                mean = sum(daily_changes) / len(daily_changes)
                std = math.sqrt(sum((x - mean) ** 2 for x in daily_changes) / len(daily_changes))
                if std > 0:
                    zscore = (intraday_pct - mean) / std

        # 6. 获取关联板块行情
        board_secid = self.boards.get(board_name, "")
        board_snap = None
        if board_secid:
            board_snap = self.data_fetcher.fetch_board_snapshot(board_secid)

        # 7. 生成建议
        actions, advice, urgency = self._generate_advice(
            profit_pct, intraday_pct, zscore, days_held, fee,
            board_snap, board_name
        )

        return {
            "code": fund_code,
            "name": est["name"] if est else fund_code,
            "entry_date": entry_date,
            "entry_nav": entry_nav,
            "entry_amount": entry_amount,
            "current_nav": round(current_nav, 4),
            "current_value": round(current_value, 2),
            "profit": round(profit, 2),
            "profit_pct": round(profit_pct, 2),
            "intraday_pct": round(intraday_pct, 2),
            "days_held": days_held,
            "volatility_zscore": round(zscore, 2),
            "board": board_name,
            "board_change_pct": round(board_snap["change_pct"], 2) if board_snap else None,
            "fee": fee,
            "overall_advice": advice,
            "urgency": urgency,
            "actions": actions,
        }

    def _generate_advice(self, profit_pct: float, intraday_pct: float,
                         zscore: float, days_held: int, fee: Dict,
                         board_snap: Optional[Dict], board_name: str) -> Tuple[List, str, str]:
        """生成单只基金的操作建议 (核心逻辑)"""
        actions = []
        advice = "HOLD"
        urgency = "low"

        sl = self.risk_config.get("stop_loss_pct", -0.08) * 100
        tp_short = self.risk_config.get("take_profit_short_pct", 0.12) * 100
        tp_trend = self.risk_config.get("take_profit_trend_pct", 0.18) * 100
        min_hold = self.risk_config.get("min_hold_for_stop", 7)

        # === 1. 费率锁定 (最高优先级) ===
        if fee["severity"] == "BLOCK":
            actions.append({
                "type": "FEE_LOCKED",
                "message": f"🔒 费率锁定: 持有{days_held}天 < {fee['lock_days']}天, 赎回费{fee['fee_label']}",
                "detail": fee["rule"],
                "countdown": fee["remaining_days"],
            })
            advice = "FEE_LOCKED"
            urgency = "critical"

            # 即使亏损也不止损
            if profit_pct < sl:
                actions.append({
                    "type": "FEE_LOCKED_LOSS",
                    "message": f"⚠️ 触发止损线({profit_pct:.1f}%)，但因费率锁定暂不执行",
                    "detail": f"{fee['fee_label']}罚息 > 止损节省, 解锁日({fee['unlock_date']})优先评估",
                })
            return actions, advice, urgency

        # === 2. 止损检查 (2:30立即判) ===
        if profit_pct <= sl:
            if days_held >= min_hold:
                net_loss = abs(profit_pct) + fee["fee_rate"] * 100
                actions.append({
                    "type": "STOP_LOSS",
                    "message": f"🔴 止损: 亏损{profit_pct:.1f}%，费率{fee['fee_label']}，净损失{net_loss:.1f}%",
                    "detail": "建议赎回止损",
                })
                advice = "STOP_LOSS"
                urgency = "critical"
            else:
                actions.append({
                    "type": "STOP_LOSS_WATCH",
                    "message": f"🟡 接近止损({profit_pct:.1f}%)，持有{days_held}天(费率{fee['fee_label']})",
                    "detail": f"距解锁还有{fee['remaining_days']}天，密切监控",
                })
                urgency = "high"

        # === 3. 止盈检查 (2:30立即判) ===
        if profit_pct >= tp_short:
            if profit_pct >= tp_trend:
                net = profit_pct - fee["fee_rate"] * 100
                actions.append({
                    "type": "TAKE_PROFIT_TREND",
                    "message": f"🟢 趋势止盈: 盈利{profit_pct:.1f}% >= {tp_trend}%，净赚{net:.1f}%",
                    "detail": "建议赎回止盈 (可分批: 先赎50%)",
                })
                advice = "TAKE_PROFIT"
                urgency = "high"
            elif days_held <= 20:
                net = profit_pct - fee["fee_rate"] * 100
                actions.append({
                    "type": "TAKE_PROFIT_SHORT",
                    "message": f"🟢 短线止盈: 盈利{profit_pct:.1f}%，净赚{net:.1f}%",
                    "detail": "短线持仓已达目标，建议赎回",
                })
                advice = "TAKE_PROFIT"
                urgency = "high"

        # === 4. 波动率异常检查 (z-score) ===
        if abs(zscore) > self.config.get("advisor", {}).get("volatility_zscore_threshold", 1.5):
            if zscore < -1.5 and profit_pct > 0:
                actions.append({
                    "type": "VOLATILITY_ALERT",
                    "message": f"🟡 异常波动: 日内跌{intraday_pct:.1f}% (z-score={zscore:.1f}σ)",
                    "detail": "今日跌幅显著高于历史常态，关注尾盘走势",
                })
                if advice == "HOLD":
                    urgency = "normal"
            elif zscore > 1.5 and profit_pct < -3:
                actions.append({
                    "type": "REBOUND_SIGNAL",
                    "message": f"🔵 异常反弹: 日内涨{intraday_pct:.1f}% (z-score={zscore:.1f}σ)",
                    "detail": "今日涨幅显著高于历史常态，可能是加仓机会",
                })
                if advice == "HOLD":
                    advice = "WATCH_ADD"

        # === 5. 板块联动检查 ===
        if board_snap:
            b_pct = board_snap.get("change_pct", 0)
            if b_pct < -2 and profit_pct > 0:
                actions.append({
                    "type": "BOARD_WEAK",
                    "message": f"📊 板块({board_name})跌{b_pct:.1f}%，但持仓盈利{profit_pct:.1f}%",
                    "detail": "板块走弱可能拖累基金，关注尾盘",
                })
            elif b_pct > 2 and profit_pct < -3:
                actions.append({
                    "type": "BOARD_STRONG",
                    "message": f"📊 板块({board_name})涨{b_pct:.1f}%，但持仓亏损{profit_pct:.1f}%",
                    "detail": "基金跑输板块，可能选股偏离，关注持续性",
                })

        # === 6. 默认持有 ===
        if not actions:
            actions.append({
                "type": "HOLD",
                "message": f"⏸ 持有观察: 盈利{profit_pct:.1f}%，费率{fee['fee_label']}",
                "detail": "当前无特殊操作信号",
            })

        return actions, advice, urgency

    def scan_new_opportunities(self, market_env: Dict) -> List[Dict]:
        """扫描未持仓板块的买入机会 (2:30只做监控，不执行)"""
        opportunities = []
        top_boards, bottom_boards = self.data_fetcher.fetch_board_ranking(top_n=5)

        for b in top_boards[:3]:
            if b.get("change_pct", 0) > 2.5:
                opportunities.append({
                    "type": "NEW_OPPORTUNITY",
                    "board": b["name"],
                    "change_pct": b["change_pct"],
                    "message": f"🔥 {b['name']}涨{b['change_pct']:.1f}%，强势板块",
                    "action": "收盘后评估是否匹配C类基金",
                    "market_env": market_env["label"],
                })

        return opportunities

    def run(self) -> Dict:
        """主入口: 执行14:30研判"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Afternoon Advisor v2 启动...")

        # 1. 加载持仓
        if not os.path.exists(self.positions_file):
            print(f"[ERROR] 找不到 {self.positions_file}")
            return {"error": "无持仓数据"}

        with open(self.positions_file, "r", encoding="utf-8") as f:
            positions_data = json.load(f)
        positions = positions_data.get("positions", {})

        if not positions:
            return {"error": "无持仓"}

        # 2. 市场环境
        market_env = self.assess_market_environment()
        market_volume = self.data_fetcher.fetch_market_volume()
        print(f"  环境: {market_env['label']} | 成交额: {market_volume}亿")

        # 3. 分析每只持仓
        results = []
        for code, pos in positions.items():
            result = self.analyze_fund(
                fund_code=code,
                entry_nav=pos.get("entry_nav", 0),
                entry_amount=pos.get("amount", 0),
                entry_date=pos.get("entry_date", ""),
                board_name=pos.get("board", ""),
            )
            results.append(result)
            adv = result["overall_advice"]
            fee_lbl = result["fee"]["fee_label"]
            print(f"    {result['name'][:12]}: {result['profit_pct']:+.1f}% | {adv} | 费率{fee_lbl}")
            time.sleep(0.3)

        # 4. 扫描新机会
        opportunities = self.scan_new_opportunities(market_env)

        # 5. 构建输出
        output = {
            "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "market": {**market_env, "volume_yi": market_volume},
            "positions": results,
            "opportunities": opportunities,
            "stats": self._calc_stats(results),
            "action_items": self._extract_actions(results),
            "fee_calendar": self.fee_manager.get_fee_calendar([
                {"code": r["code"], "name": r["name"], "entry_date": r["entry_date"]}
                for r in results
            ]),
        }

        # 6. 写入文件
        output_file = os.path.join(self.output_dir, "afternoon_advice.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  输出: {output_file}")
        return output

    def _calc_stats(self, results: List[Dict]) -> Dict:
        total_invested = sum(r["entry_amount"] for r in results)
        total_profit = sum(r["profit"] for r in results)
        return {
            "total_holdings": len(results),
            "critical_count": sum(1 for r in results if r["urgency"] == "critical"),
            "high_count": sum(1 for r in results if r["urgency"] == "high"),
            "total_invested": round(total_invested, 2),
            "total_profit": round(total_profit, 2),
            "total_profit_pct": round(total_profit / total_invested * 100, 2) if total_invested > 0 else 0,
        }

    def _extract_actions(self, results: List[Dict]) -> List[Dict]:
        actions = []
        order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        for r in sorted(results, key=lambda x: order.get(x["urgency"], 99)):
            for a in r["actions"]:
                if a["type"] != "HOLD":
                    actions.append({
                        "urgency": r["urgency"],
                        "fund_code": r["code"],
                        "fund_name": r["name"],
                        "type": a["type"],
                        "message": a["message"],
                    })
        return actions
