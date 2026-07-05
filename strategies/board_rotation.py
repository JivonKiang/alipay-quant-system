"""
Board Rotation Strategy — 板块轮动策略
参考: quick_money.py 板块扫描 + Qlib 行业轮动因子
"""
from typing import List, Dict
from strategies.base import BaseStrategy


class BoardRotationStrategy(BaseStrategy):
    """
    板块轮动策略: 基于板块相对强弱排名进行轮动
    买入当日涨幅Top N板块关联基金，卖出跌幅Bottom N板块关联基金
    """

    def __init__(self, config: Dict = None):
        super().__init__("Board_Rotation", config)
        self.top_n = config.get("top_n", 5) if config else 5
        self.lookback = config.get("lookback", 5) if config else 5
        self.min_change_pct = config.get("min_change_pct", 0.02) if config else 0.02

    def generate_signals(self, data: List[Dict]) -> List[Dict]:
        """
        生成板块轮动信号
        data: 板块日数据列表, 每项包含:
            {date, board_name, change_pct, volume_ratio, ma10, ma20}
        """
        if not data:
            return []

        # 按日期分组
        by_date = {}
        for d in data:
            dt = d.get("date", "")
            if dt not in by_date:
                by_date[dt] = []
            by_date[dt].append(d)

        signals = []
        sorted_dates = sorted(by_date.keys())

        for dt in sorted_dates:
            boards = by_date[dt]
            if len(boards) < self.top_n * 2:
                continue

            # 按涨跌幅排序
            boards_sorted = sorted(boards, key=lambda x: x.get("change_pct", 0), reverse=True)

            # Top N 强势板块 → 买入信号
            for b in boards_sorted[:self.top_n]:
                if b.get("change_pct", 0) > self.min_change_pct:
                    signals.append({
                        "date": dt,
                        "action": "BUY",
                        "board": b.get("board_name", ""),
                        "reason": f"板块涨幅{b['change_pct']:.1f}%, 排名Top{self.top_n}",
                        "strength": "strong" if b.get("change_pct", 0) > self.min_change_pct * 2 else "medium",
                        "change_pct": b.get("change_pct", 0),
                        "rank": boards_sorted.index(b) + 1,
                    })

            # Bottom N 弱势板块 → 卖出信号
            for b in boards_sorted[-self.top_n:]:
                if b.get("change_pct", 0) < -self.min_change_pct:
                    signals.append({
                        "date": dt,
                        "action": "SELL",
                        "board": b.get("board_name", ""),
                        "reason": f"板块跌幅{b['change_pct']:.1f}%, 排名Bottom{self.top_n}",
                        "strength": "strong" if b.get("change_pct", 0) < -self.min_change_pct * 2 else "medium",
                        "change_pct": b.get("change_pct", 0),
                        "rank": len(boards_sorted) - boards_sorted[::-1].index(b),
                    })

        return signals

    def get_params(self) -> Dict:
        return {
            "top_n": self.top_n,
            "lookback": self.lookback,
            "min_change_pct": self.min_change_pct,
        }
