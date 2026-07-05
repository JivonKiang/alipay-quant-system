"""
Tests for Backtest Engine
TDD: RED-GREEN-REFACTOR
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.backtest import BacktestEngine
from strategies.ma_strategy import MACrossoverStrategy


def test_ma_strategy_backtest():
    """测试MA策略回测"""
    # 构造测试数据 (模拟基金净值)
    # 设计: 先下跌(产生金叉) → 再上涨(持仓) → 再下跌(产生死叉)
    # 确保 MA10/MA20 能形成完整的交叉信号
    data = []
    price = 1.0
    for i in range(150):
        if i < 30:
            # 前30天震荡下跌: 跌5天弹2天, 形成MA10<MA20
            price *= 0.996 if i % 7 < 5 else 1.004
        elif i < 80:
            # 中间50天持续上涨: MA10上穿MA20 (金叉)
            price *= 1.005
        else:
            # 后70天下跌: MA10下穿MA20 (死叉)
            price *= 0.995
        data.append({"date": f"2024-01-{i+1:02d}", "nav": round(price, 4)})

    engine = BacktestEngine({"initial_capital": 100000, "commission_rate": 0.00015, "slippage": 0.001})
    strategy = MACrossoverStrategy({"ma_short": 10, "ma_long": 20})

    result = engine.run(strategy, data)

    assert "error" not in result, f"回测错误: {result.get('error')}"
    assert result["trades_count"] > 0, "策略应产生交易信号"
    assert result["final_value"] > 0, "最终资产应大于0"
    assert "metrics" in result, "应包含绩效指标"
    assert "sharpe_ratio" in result["metrics"], "应包含夏普比率"

    print(f"✅ MA回测通过: {result['trades_count']}笔交易, 总收益{result['total_return_pct']:.1f}%, 夏普{result['metrics']['sharpe_ratio']:.2f}")


def test_multi_strategy_comparison():
    """测试多策略对比"""
    from strategies.momentum_strategy import MomentumStrategy

    data = []
    price = 1.0
    for i in range(100):
        price *= 1.002 if i % 10 < 5 else 0.998
        data.append({"date": f"2024-01-{i+1:02d}", "nav": round(price, 4)})

    engine = BacktestEngine({"initial_capital": 100000, "commission_rate": 0.00015, "slippage": 0.001})
    strategies = [
        MACrossoverStrategy({"ma_short": 5, "ma_long": 10}),
        MomentumStrategy({"lookback": 10, "buy_threshold": 0.02, "sell_threshold": -0.02}),
    ]

    result = engine.compare_strategies(strategies, data)
    assert "comparison" in result
    assert len(result["comparison"]) == 2
    assert result["best_strategy"] is not None

    print(f"✅ 多策略对比通过: 最佳策略={result['best_strategy']}")


if __name__ == "__main__":
    test_ma_strategy_backtest()
    test_multi_strategy_comparison()
    print("\n🎉 All backtest tests passed!")
