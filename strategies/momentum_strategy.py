"""
Momentum Strategy — 动量策略
参考: quick_money.py Momentum-60策略 + Qlib Alpha因子
"""
from typing import List, Dict
from strategies.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """动量策略: N日收益率超过阈值时买入，低于阈值时卖出"""

    def __init__(self, config: Dict = None):
        super().__init__("Momentum", config)
        self.lookback = config.get("lookback", 60) if config else 60
        self.buy_threshold = config.get("buy_threshold", 0.05) if config else 0.05
        self.sell_threshold = config.get("sell_threshold", -0.03) if config else -0.03

    def generate_signals(self, data: List[Dict]) -> List[Dict]:
        """
        生成动量信号
        data: [{date, nav}, ...]
        """
        if len(data) < self.lookback + 5:
            return []

        prices = [d["nav"] for d in data]
        dates = [d["date"] for d in data]

        signals = []
        for i in range(self.lookback, len(prices)):
            past_price = prices[i - self.lookback]
            curr_price = prices[i]
            momentum = (curr_price - past_price) / past_price if past_price > 0 else 0

            if momentum > self.buy_threshold:
                signals.append({
                    "date": dates[i],
                    "action": "BUY",
                    "reason": f"{self.lookback}日动量 {momentum*100:.1f}% > 阈值 {self.buy_threshold*100:.1f}%",
                    "strength": "strong" if momentum > self.buy_threshold * 1.5 else "medium",
                    "price": curr_price,
                    "momentum": round(momentum, 4),
                })
            elif momentum < self.sell_threshold:
                signals.append({
                    "date": dates[i],
                    "action": "SELL",
                    "reason": f"{self.lookback}日动量 {momentum*100:.1f}% < 阈值 {self.sell_threshold*100:.1f}%",
                    "strength": "strong" if momentum < self.sell_threshold * 1.5 else "medium",
                    "price": curr_price,
                    "momentum": round(momentum, 4),
                })

        return signals

    def get_params(self) -> Dict:
        return {
            "lookback": self.lookback,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
        }
