"""
Metrics — 量化绩效指标计算
参考: VectorBT stats 模块 + LEAN 绩效报告
"""
import math
from typing import List, Dict


def calculate_metrics(returns: List[float], capital: float = 100000) -> Dict:
    """
    计算完整绩效指标
    returns: 每日收益率列表 (小数形式, 如 0.01 = 1%)
    """
    if not returns or len(returns) < 2:
        return {"error": "收益率数据不足"}

    n = len(returns)

    # 累计收益
    cum_returns = [1.0]
    for r in returns:
        cum_returns.append(cum_returns[-1] * (1 + r))
    total_return = cum_returns[-1] - 1

    # 年化收益 (假设252个交易日)
    annual_return = (1 + total_return) ** (252 / n) - 1

    # 波动率
    avg_return = sum(returns) / n
    variance = sum((r - avg_return) ** 2 for r in returns) / n
    daily_vol = math.sqrt(variance)
    annual_vol = daily_vol * math.sqrt(252)

    # 夏普比率 (假设无风险利率 2.5%)
    rf = 0.025
    sharpe = (annual_return - rf) / annual_vol if annual_vol > 0 else 0

    # 最大回撤
    max_dd = 0
    peak = 1.0
    for cr in cum_returns[1:]:
        if cr > peak:
            peak = cr
        dd = (peak - cr) / peak
        if dd > max_dd:
            max_dd = dd

    # Sortino比率 (只计 downside)
    downside_returns = [r for r in returns if r < 0]
    downside_vol = math.sqrt(sum(r ** 2 for r in downside_returns) / n) * math.sqrt(252) if downside_returns else 0.0001
    sortino = (annual_return - rf) / downside_vol if downside_vol > 0 else 0

    # 胜率
    win_count = sum(1 for r in returns if r > 0)
    win_rate = win_count / n

    # 盈亏比
    avg_win = sum(r for r in returns if r > 0) / win_count if win_count > 0 else 0
    loss_count = n - win_count
    avg_loss = abs(sum(r for r in returns if r < 0) / loss_count) if loss_count > 0 else 0.0001
    profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

    # Calmar比率
    calmar = annual_return / max_dd if max_dd > 0 else 0

    return {
        "total_return": round(total_return * 100, 2),
        "annual_return": round(annual_return * 100, 2),
        "annual_volatility": round(annual_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "calmar_ratio": round(calmar, 3),
        "win_rate": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 3),
        "avg_daily_return": round(avg_return * 100, 4),
        "trading_days": n,
    }


def calculate_alpha_beta(strategy_returns: List[float], benchmark_returns: List[float]) -> Dict:
    """
    计算 Alpha / Beta (相对于基准)
    """
    if len(strategy_returns) != len(benchmark_returns) or len(strategy_returns) < 2:
        return {"error": "数据长度不匹配或不足"}

    n = len(strategy_returns)
    avg_s = sum(strategy_returns) / n
    avg_b = sum(benchmark_returns) / n

    # Beta = Cov(s, b) / Var(b)
    cov = sum((s - avg_s) * (b - avg_b) for s, b in zip(strategy_returns, benchmark_returns)) / n
    var_b = sum((b - avg_b) ** 2 for b in benchmark_returns) / n
    beta = cov / var_b if var_b > 0 else 0

    # Alpha = avg_s - beta * avg_b
    alpha = avg_s - beta * avg_b

    # 相关系数
    std_s = math.sqrt(sum((s - avg_s) ** 2 for s in strategy_returns) / n)
    std_b = math.sqrt(var_b)
    correlation = cov / (std_s * std_b) if std_s > 0 and std_b > 0 else 0

    return {
        "alpha": round(alpha * 100, 4),
        "beta": round(beta, 3),
        "correlation": round(correlation, 3),
    }
