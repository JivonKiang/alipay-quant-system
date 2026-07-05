"""
MA Crossover Strategy — 双均线交叉策略
参考: trading_system.py MA60-120策略 + Backtrader 经典实现
"""
from typing import List, Dict
from strategies.base import BaseStrategy


class MACrossoverStrategy(BaseStrategy):
    """MA双均线交叉策略: MA_SHORT上穿MA_LONG买入，下穿卖出"""

    def __init__(self, config: Dict = None):
        super().__init__("MA_Crossover", config)
        self.ma_short = config.get("ma_short", 60) if config else 60
        self.ma_long = config.get("ma_long", 120) if config else 120

    def _calculate_ma(self, prices: List[float], period: int) -> List[float]:
        """计算简单移动平均"""
        if len(prices) < period:
            return []
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(None)
            else:
                ma.append(sum(prices[i - period + 1:i + 1]) / period)
        return ma

    def generate_signals(self, data: List[Dict]) -> List[Dict]:
        """
        生成MA交叉信号
        data: [{date, nav}, ...]
        """
        if len(data) < self.ma_long + 5:
            return []

        prices = [d["nav"] for d in data]
        dates = [d["date"] for d in data]

        ma_s = self._calculate_ma(prices, self.ma_short)
        ma_l = self._calculate_ma(prices, self.ma_long)

        signals = []
        for i in range(self.ma_long, len(prices)):
            if ma_s[i] is None or ma_l[i] is None:
                continue

            prev_s = ma_s[i - 1]
            prev_l = ma_l[i - 1]
            curr_s = ma_s[i]
            curr_l = ma_l[i]

            if prev_s is None or prev_l is None:
                continue

            # 金叉: 短均线上穿长均线
            if prev_s <= prev_l and curr_s > curr_l:
                signals.append({
                    "date": dates[i],
                    "action": "BUY",
                    "reason": f"MA{self.ma_short}上穿MA{self.ma_long} (金叉)",
                    "strength": "strong",
                    "price": prices[i],
                    "ma_short": round(curr_s, 4),
                    "ma_long": round(curr_l, 4),
                })
            # 死叉: 短均线下穿长均线
            elif prev_s >= prev_l and curr_s < curr_l:
                signals.append({
                    "date": dates[i],
                    "action": "SELL",
                    "reason": f"MA{self.ma_short}下穿MA{self.ma_long} (死叉)",
                    "strength": "strong",
                    "price": prices[i],
                    "ma_short": round(curr_s, 4),
                    "ma_long": round(curr_l, 4),
                })

        return signals

    def get_params(self) -> Dict:
        return {"ma_short": self.ma_short, "ma_long": self.ma_long}
