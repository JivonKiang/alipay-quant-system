"""
Position Sizer — 动态仓位管理
参考: Freqtrade 仓位管理 + LEAN 组合优化
"""
from typing import Dict


class PositionSizer:
    """动态仓位管理器"""

    def __init__(self, config: Dict):
        self.total_flexible = config.get("total_flexible", 96000)
        self.single_trade_max = config.get("single_trade_max", 5000)
        self.single_fund_max_pct = config.get("single_fund_max_pct", 0.20)
        self.max_concurrent = config.get("max_concurrent_signals", 2)
        self.sizing_rules = config.get("position_sizing", {
            "bull": {"amount": 5000, "label": "牛市"},
            "bull_lean": {"amount": 4000, "label": "偏多"},
            "range": {"amount": 3000, "label": "震荡"},
            "bear_lean": {"amount": 2000, "label": "偏熊"},
            "bear": {"amount": 1000, "label": "熊市"},
        })

    def get_trade_amount(self, market_env: str, signal_strength: str = "medium") -> int:
        """
        根据市场环境确定单次买入金额
        signal_strength: strong / medium / weak
        """
        base = self.sizing_rules.get(market_env, {}).get("amount", 3000)

        # 信号强度调整
        multipliers = {"strong": 1.0, "medium": 0.7, "weak": 0.4}
        multiplier = multipliers.get(signal_strength, 0.7)

        amount = int(base * multiplier)
        return min(amount, self.single_trade_max)

    def get_max_position_value(self) -> float:
        """单基金最大持仓金额"""
        return self.total_flexible * self.single_fund_max_pct

    def can_open_new_position(self, current_holdings_count: int) -> bool:
        """是否可以开新仓"""
        return current_holdings_count < self.max_concurrent

    def calculate_position_pct(self, position_value: float, total_invested: float) -> float:
        """计算单基金仓位占比"""
        if total_invested <= 0:
            return 0
        return position_value / total_invested

    def is_over_weight(self, position_value: float) -> bool:
        """是否超仓"""
        return position_value > self.get_max_position_value()
