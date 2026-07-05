"""
Alipay Quant System — 主入口
参考: Qlib (流水线) + Freqtrade (多模式) + Superpowers (TDD)

运行模式:
  python main.py recommend                    # 热门板块→基金筛选→回测→推荐报告
  python main.py recommend --type industry    # 按行业板块扫描
  python main.py recommend --boards 3 --funds 5 --output report.json
  python main.py backtest --fund 005844 --strategy ma --days 252
  python main.py advisor                      # 14:30 场内研判
  python main.py advisor --notify             # 14:30 研判 + Telegram推送
  python main.py test                         # 运行所有测试
"""
import sys
import os
import argparse

# 确保模块路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from engine.data_fetcher import DataFetcher
from engine.backtest import BacktestEngine
from engine.metrics import calculate_metrics
from strategies.ma_strategy import MACrossoverStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.board_rotation import BoardRotationStrategy
from advisor.afternoon_advisor import AfternoonAdvisor
from advisor.recommendation_engine import RecommendationEngine
from advisor.report_formatter import ReportFormatter
from notify.telegram_bot import TelegramNotifier
from risk.fee_manager import FeeManager


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_backtest(args):
    """回测命令"""
    config = load_config()
    fetcher = DataFetcher()
    engine = BacktestEngine(config.get("backtest", {}))

    print(f"📊 正在获取 {args.fund} 的历史数据...")
    data = fetcher.fetch_fund_nav(args.fund, args.days)
    if not data:
        print(f"❌ 无法获取 {args.fund} 的数据")
        return

    # 反转数据（从旧到新）
    data = list(reversed(data))

    strategies = []
    if args.strategy == "ma" or args.strategy == "all":
        strategies.append(MACrossoverStrategy(config.get("strategies", {}).get("ma", {})))
    if args.strategy == "momentum" or args.strategy == "all":
        strategies.append(MomentumStrategy(config.get("strategies", {}).get("momentum", {})))
    if args.strategy == "board" or args.strategy == "all":
        strategies.append(BoardRotationStrategy(config.get("strategies", {}).get("board", {})))

    if len(strategies) == 1:
        result = engine.run(strategies[0], data)
        print_result(result)
    else:
        result = engine.compare_strategies(strategies, data)
        print("\n📈 多策略对比结果:")
        print("-" * 60)
        for r in result["comparison"]:
            print(f"  {r['strategy']:20s}  收益:{r['total_return']:+.1f}%  夏普:{r['sharpe']:.2f}  回撤:{r['max_dd']:.1f}%  交易:{r['trades']}笔")
        print(f"\n🏆 最佳策略: {result['best_strategy']}")


def print_result(result: dict):
    """打印回测结果"""
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print(f"\n📈 回测结果: {result['strategy']}")
    print(f"  参数: {result['params']}")
    print(f"  初始资金: ¥{result['initial_capital']:,}")
    print(f"  最终资产: ¥{result['final_value']:,}")
    print(f"  总收益率: {result['total_return_pct']:+.2f}%")
    print(f"  交易次数: {result['trades_count']}笔")

    m = result.get("metrics", {})
    print(f"\n📊 绩效指标:")
    print(f"  年化收益: {m.get('annual_return', 0):+.2f}%")
    print(f"  年化波动: {m.get('annual_volatility', 0):.2f}%")
    print(f"  夏普比率: {m.get('sharpe_ratio', 0):.3f}")
    print(f"  Sortino:  {m.get('sortino_ratio', 0):.3f}")
    print(f"  最大回撤: {m.get('max_drawdown', 0):.2f}%")
    print(f"  Calmar:   {m.get('calmar_ratio', 0):.3f}")
    print(f"  胜率:     {m.get('win_rate', 0):.1f}%")
    print(f"  盈亏比:   {m.get('profit_factor', 0):.3f}")

    ab = result.get("alpha_beta")
    if ab:
        print(f"\n📐 基准对比:")
        print(f"  Alpha: {ab.get('alpha', 0):.4f}%")
        print(f"  Beta:  {ab.get('beta', 0):.3f}")
        print(f"  相关性: {ab.get('correlation', 0):.3f}")

    # 打印最近5笔交易
    trades = result.get("trades", [])
    if trades:
        print(f"\n💼 最近交易:")
        for t in trades[-5:]:
            print(f"  {t['date']} {t['action']:4s} ¥{t.get('cost', t.get('value', 0)):.0f} {t.get('reason', '')[:40]}")


def cmd_recommend(args):
    """推荐命令: 热门板块→基金筛选→回测→推荐报告"""
    config = load_config()

    engine_config = {
        "top_boards": args.boards,
        "top_funds_per_board": args.funds,
        "min_win_rate_7d": config.get("advisor", {}).get("min_win_rate_7d", 50),
        "min_win_rate_14d": config.get("advisor", {}).get("min_win_rate_14d", 50),
        "fee": config.get("fee", {}),
    }

    engine = RecommendationEngine(engine_config)
    report = engine.run(board_type=args.type)

    # 格式化输出
    formatter = ReportFormatter()
    output = formatter.format_terminal(report)
    print(output)

    # 保存文件
    if args.output:
        import os
        os.makedirs("output", exist_ok=True)
        json_path = args.output
        formatter.save_json(report, json_path)
        print(f"\n💾 报告已保存: {json_path}")

        # 同时保存 Markdown
        md_path = json_path.rsplit(".", 1)[0] + ".md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(formatter.format_markdown(report))
        print(f"💾 Markdown已保存: {md_path}")


def cmd_advisor(args):
    """14:30 研判命令"""
    advisor = AfternoonAdvisor()
    result = advisor.run()

    if "error" in result:
        print(f"❌ {result['error']}")
        return

    # Telegram 推送
    if args.notify:
        config = load_config()
        notifier = TelegramNotifier(config.get("telegram", {}))
        if notifier.send_advice(result):
            print("📲 Telegram 推送成功")
        else:
            print("📲 Telegram 推送失败或未配置")


def cmd_test(args):
    """运行测试"""
    import subprocess
    print("🧪 运行测试...")

    test_files = [
        "tests/test_fee_manager.py",
        "tests/test_backtest.py",
    ]

    for tf in test_files:
        print(f"\n--- {tf} ---")
        result = subprocess.run([sys.executable, tf], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)


def main():
    parser = argparse.ArgumentParser(description="Alipay Quant System")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # backtest
    p_backtest = subparsers.add_parser("backtest", help="回测策略")
    p_backtest.add_argument("--fund", required=True, help="基金代码")
    p_backtest.add_argument("--strategy", default="ma", choices=["ma", "momentum", "board", "all"], help="策略类型")
    p_backtest.add_argument("--days", type=int, default=252, help="回测天数")

    # advisor
    p_advisor = subparsers.add_parser("advisor", help="14:30 场内研判")
    p_advisor.add_argument("--notify", action="store_true", help="同时推送 Telegram")

    # recommend
    p_rec = subparsers.add_parser("recommend", help="热门板块→基金筛选→回测→推荐报告")
    p_rec.add_argument("--type", default="concept", choices=["concept", "industry"],
                       help="板块类型: concept(概念) / industry(行业)")
    p_rec.add_argument("--boards", type=int, default=5, help="扫描Top N板块")
    p_rec.add_argument("--funds", type=int, default=3, help="每板块筛选Top N基金")
    p_rec.add_argument("--output", type=str, default="output/recommendation.json",
                       help="输出文件路径")

    # test
    p_test = subparsers.add_parser("test", help="运行测试")

    args = parser.parse_args()

    if args.command == "recommend":
        cmd_recommend(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "advisor":
        cmd_advisor(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
