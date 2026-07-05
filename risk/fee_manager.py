"""
Fee Manager — C类基金费率管理
参考: quick_money.py 门控1 + Freqtrade 费率模型
"""
from datetime import datetime, date
from typing import Dict, Optional


class FeeManager:
    """C类基金费率管理器"""

    def __init__(self, config: Dict):
        self.default_lock_days = config.get("default_lock_days", 7)
        self.fee_schedule = config.get("fee_schedule", [
            {"max_days": 6,  "rate": 0.015, "label": "1.5%", "severity": "BLOCK"},
            {"max_days": 29, "rate": 0.005, "label": "0.5%", "severity": "WARN"},
            {"max_days": 9999, "rate": 0.0, "label": "0%", "severity": "OK"},
        ])
        self.custom_lock_days = config.get("custom_lock_days", {})

    def get_lock_days(self, fund_code: str) -> int:
        """获取基金锁定期天数"""
        return self.custom_lock_days.get(fund_code, self.default_lock_days)

    def get_fee_tier(self, days_held: int, fund_code: str = "") -> Dict:
        """
        获取费率等级
        返回完整费率信息字典
        """
        lock_days = self.get_lock_days(fund_code)

        for tier in self.fee_schedule:
            effective_max = tier["max_days"]

            # BLOCK 等级: 使用自定义锁定天数
            if tier["severity"] == "BLOCK":
                effective_max = lock_days - 1

            if days_held <= effective_max:
                return {
                    "days_held": days_held,
                    "fee_rate": tier["rate"],
                    "fee_label": tier["label"],
                    "severity": tier["severity"],
                    "rule": tier.get("rule", ""),
                    "lock_days": lock_days,
                    "remaining_days": max(0, lock_days - days_held),
                    "unlock_date": (date.today() + __import__("datetime").timedelta(
                        days=max(0, lock_days - days_held))).strftime("%Y-%m-%d"),
                }

        # 默认返回OK
        return {
            "days_held": days_held,
            "fee_rate": 0,
            "fee_label": "0%",
            "severity": "OK",
            "rule": "自由操作，无费率约束",
            "lock_days": lock_days,
            "remaining_days": 0,
            "unlock_date": date.today().strftime("%Y-%m-%d"),
        }

    def can_redeem(self, days_held: int, fund_code: str = "") -> bool:
        """是否可以赎回 (不受 BLOCK 限制)"""
        tier = self.get_fee_tier(days_held, fund_code)
        return tier["severity"] != "BLOCK"

    def can_add_position(self, days_held: int, fund_code: str = "") -> bool:
        """是否可以追加 (不受 BLOCK 限制)"""
        return self.can_redeem(days_held, fund_code)

    def calculate_net_return(self, gross_return_pct: float, days_held: int, fund_code: str = "") -> float:
        """
        计算扣除赎回费后的净收益
        gross_return_pct: 毛收益百分比 (如 12.5 = 12.5%)
        """
        tier = self.get_fee_tier(days_held, fund_code)
        fee = tier["fee_rate"] * 100  # 转为百分比
        return gross_return_pct - fee

    def days_held(self, entry_date_str: str) -> int:
        """计算持有天数"""
        try:
            entry_dt = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
            return (date.today() - entry_dt).days
        except:
            return 0

    def get_fee_calendar(self, holdings: list) -> list:
        """生成费率解锁日历"""
        calendar = []
        for h in holdings:
            entry_date = h.get("entry_date", "")
            fund_code = h.get("code", "")
            days = self.days_held(entry_date) if entry_date else 0
            tier = self.get_fee_tier(days, fund_code)
            if tier["severity"] != "OK":
                calendar.append({
                    "fund_code": fund_code,
                    "fund_name": h.get("name", ""),
                    "days_held": days,
                    "fee_label": tier["fee_label"],
                    "lock_days": tier["lock_days"],
                    "remaining_days": tier["remaining_days"],
                    "unlock_date": tier["unlock_date"],
                })
        return sorted(calendar, key=lambda x: x["remaining_days"])
