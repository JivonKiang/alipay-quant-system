"""
Backtest Engine — 向量化回测引擎
参考: VectorBT (向量化) + Jesse (零偏差) + Qlib (流水线)
支持: 多策略、滑点、费率、仓位管理
"""
import copy
from typing import List, Dict, Optional
from engine.metrics import calculate_metrics


class BacktestEngine:
    """向量化回测引擎"""

    def __init__(self, config: Dict):
        self.initial_capital = config.get("initial_capital", 100000)
        self.commission_rate = config.get("commission_rate", 0.00015)
        self.slippage = config.get("slippage", 0.001)

    def run(self, strategy, data: List[Dict], benchmark_data: List[Dict] = None) -> Dict:
        """
        运行回测
        strategy: 策略实例 (必须继承 BaseStrategy)
        data: [{date, nav, ...}, ...] 基金历史数据
        benchmark_data: 基准数据 (可选, 用于计算Alpha/Beta)
        """
        if not data or len(data) < 30:
            return {"error": "数据不足，无法回测"}

        # 生成信号
        signals = strategy.generate_signals(data)
        if not signals:
            return {"error": "策略未生成任何信号"}

        # 构建日期->信号映射
        signal_map = {}
        for s in signals:
            dt = s["date"]
            if dt not in signal_map:
                signal_map[dt] = []
            signal_map[dt].append(s)

        # 回测状态
        capital = self.initial_capital
        position = 0  # 持仓份额
        trades = []
        daily_values = []
        daily_returns = []

        for i, row in enumerate(data):
            date = row["date"]
            price = row["nav"]

            # 当日信号
            day_signals = signal_map.get(date, [])

            for sig in day_signals:
                action = sig["action"]

                if action == "BUY" and capital > 0:
                    # 买入: 扣除手续费和滑点
                    effective_price = price * (1 + self.slippage)
                    trade_amount = min(capital * 0.3, capital)  # 每次最多30%资金
                    shares = trade_amount / effective_price
                    cost = trade_amount * (1 + self.commission_rate)

                    if cost <= capital:
                        capital -= cost
                        position += shares
                        trades.append({
                            "date": date,
                            "action": "BUY",
                            "price": round(effective_price, 4),
                            "shares": round(shares, 2),
                            "cost": round(cost, 2),
                            "reason": sig.get("reason", ""),
                        })

                elif action == "SELL" and position > 0:
                    # 卖出: 扣除手续费和滑点
                    effective_price = price * (1 - self.slippage)
                    sell_value = position * effective_price
                    fee = sell_value * self.commission_rate
                    net_value = sell_value - fee

                    capital += net_value
                    trades.append({
                        "date": date,
                        "action": "SELL",
                        "price": round(effective_price, 4),
                        "shares": round(position, 2),
                        "value": round(sell_value, 2),
                        "fee": round(fee, 2),
                        "net": round(net_value, 2),
                        "reason": sig.get("reason", ""),
                    })
                    position = 0

            # 计算当日资产总值
            market_value = position * price if position > 0 else 0
            total_value = capital + market_value
            daily_values.append({"date": date, "value": round(total_value, 2)})

            # 计算日收益率
            if i > 0:
                prev_value = daily_values[i - 1]["value"]
                daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0
                daily_returns.append(daily_return)

        # 最终状态
        final_price = data[-1]["nav"]
        final_value = capital + position * final_price
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # 绩效指标
        metrics = calculate_metrics(daily_returns, self.initial_capital)

        # 基准对比
        alpha_beta = None
        if benchmark_data and len(benchmark_data) == len(data):
            bench_returns = []
            for i in range(1, len(benchmark_data)):
                prev = benchmark_data[i - 1]["nav"]
                curr = benchmark_data[i]["nav"]
                bench_returns.append((curr - prev) / prev if prev > 0 else 0)

            if len(bench_returns) == len(daily_returns):
                from engine.metrics import calculate_alpha_beta
                alpha_beta = calculate_alpha_beta(daily_returns, bench_returns)

        return {
            "strategy": strategy.name,
            "params": strategy.get_params(),
            "initial_capital": self.initial_capital,
            "final_value": round(final_value, 2),
            "total_return_pct": round(total_return * 100, 2),
            "trades_count": len(trades),
            "trades": trades,
            "daily_values": daily_values,
            "metrics": metrics,
            "alpha_beta": alpha_beta,
        }

    def compare_strategies(self, strategies: List, data: List[Dict]) -> Dict:
        """多策略对比回测"""
        results = []
        for strategy in strategies:
            result = self.run(strategy, data)
            results.append({
                "strategy": strategy.name,
                "total_return": result.get("total_return_pct", 0),
                "sharpe": result.get("metrics", {}).get("sharpe_ratio", 0),
                "max_dd": result.get("metrics", {}).get("max_drawdown", 0),
                "trades": result.get("trades_count", 0),
                "full": result,
            })

        # 按总收益排序
        results.sort(key=lambda x: x["total_return"], reverse=True)
        return {
            "comparison": results,
            "best_strategy": results[0]["strategy"] if results else None,
        }
