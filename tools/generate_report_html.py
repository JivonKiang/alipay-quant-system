"""
Generate HTML Report — 将 JSON 推荐报告转换为静态 HTML
用于 GitHub Pages 部署
"""
import json
import os
import sys
from datetime import datetime


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>支付宝C类基金推荐报告 — {{report_time}}</title>
<style>
:root {
  --bg: #0a0f1e;
  --bg2: #111827;
  --bg3: #1a2332;
  --ink: #e8ecf1;
  --muted: #8892a4;
  --rule: #2a3444;
  --accent: #00d4aa;
  --accent2: #f59e0b;
  --accent3: #3b82f6;
  --danger: #ef4444;
  --success: #22c55e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.7;
  min-height: 100vh;
}
.container { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }

/* Header */
.header {
  text-align: center;
  padding: 2.5rem 1rem;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 2rem;
}
.header h1 { font-size: 1.8rem; font-weight: 700; color: #fff; margin-bottom: 0.5rem; }
.header .meta { color: var(--muted); font-size: 0.9rem; }
.header .badge {
  display: inline-block; background: var(--accent); color: var(--bg);
  font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.7rem;
  border-radius: 4px; margin-top: 0.75rem; letter-spacing: 0.03em;
}

/* Summary cards */
.summary-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem; margin-bottom: 2rem;
}
.summary-card {
  background: var(--bg2); border: 1px solid var(--rule); border-radius: 10px;
  padding: 1.25rem; text-align: center;
}
.summary-card .value {
  font-size: 1.6rem; font-weight: 700; color: var(--accent); margin-bottom: 0.25rem;
}
.summary-card .label { font-size: 0.8rem; color: var(--muted); }

/* Section */
.section { margin-bottom: 2.5rem; }
.section h2 {
  font-size: 1.2rem; font-weight: 700; color: #fff;
  padding-bottom: 0.5rem; border-bottom: 2px solid var(--accent);
  margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;
}

/* Table */
.table-wrap { overflow-x: auto; border-radius: 8px; border: 1px solid var(--rule); }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th { background: var(--bg3); color: var(--accent); font-weight: 600; padding: 0.75rem 0.5rem; text-align: left; }
td { padding: 0.6rem 0.5rem; border-bottom: 1px solid var(--rule); color: var(--ink); }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(0,212,170,0.03); }
.pos { color: var(--danger); }
.neg { color: var(--success); }
.num { font-family: "SF Mono", "Fira Code", monospace; font-size: 0.85rem; }

/* Fund card */
.fund-card {
  background: var(--bg2); border: 1px solid var(--rule); border-radius: 12px;
  padding: 1.5rem; margin-bottom: 1.25rem;
  transition: border-color 0.2s;
}
.fund-card:hover { border-color: var(--accent); }
.fund-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem;
}
.fund-title { font-size: 1.1rem; font-weight: 700; color: #fff; }
.fund-code {
  font-family: "SF Mono", monospace; font-size: 0.8rem; color: var(--accent);
  background: rgba(0,212,170,0.1); padding: 0.15rem 0.5rem; border-radius: 4px;
}
.fund-board {
  font-size: 0.82rem; color: var(--muted); margin-top: 0.25rem;
}
.fund-score {
  font-size: 1.4rem; font-weight: 700; color: var(--accent2);
}
.fund-score-label { font-size: 0.7rem; color: var(--muted); text-align: right; }

/* Metrics grid */
.metrics-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.75rem; margin: 1rem 0;
}
.metric {
  background: var(--bg3); border-radius: 8px; padding: 0.75rem;
}
.metric .value { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
.metric .label { font-size: 0.72rem; color: var(--muted); }

/* Reasons & Risks */
.reasons, .risks { margin-top: 1rem; }
.reasons h4 { color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem; }
.risks h4 { color: var(--accent2); font-size: 0.9rem; margin-bottom: 0.5rem; }
.reasons ul, .risks ul { list-style: none; padding: 0; }
.reasons li {
  font-size: 0.85rem; color: var(--ink); padding: 0.35rem 0;
  padding-left: 1.2rem; position: relative;
}
.reasons li::before { content: "✓"; position: absolute; left: 0; color: var(--accent); }
.risks li {
  font-size: 0.85rem; color: var(--ink); padding: 0.35rem 0;
  padding-left: 1.2rem; position: relative;
}
.risks li::before { content: "!"; position: absolute; left: 0; color: var(--accent2); font-weight: 700; }

/* Footer */
.footer {
  text-align: center; padding: 2rem; border-top: 1px solid var(--rule);
  color: var(--muted); font-size: 0.82rem;
}
.footer a { color: var(--accent); text-decoration: none; }

/* Fee banner */
.fee-banner {
  background: linear-gradient(90deg, rgba(239,68,68,0.1), rgba(245,158,11,0.1));
  border: 1px solid rgba(239,68,68,0.2); border-radius: 8px;
  padding: 0.75rem 1rem; margin-top: 1rem; font-size: 0.82rem;
  color: var(--accent2);
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>支付宝C类基金量化推荐报告</h1>
    <div class="meta">生成时间: {{report_time}} | 基于历史数据滚动窗口回测</div>
    <div class="badge">仅供参考，不构成投资建议</div>
  </div>

  <!-- Summary -->
  <div class="summary-grid">
    <div class="summary-card">
      <div class="value">{{boards_count}}</div>
      <div class="label">扫描板块</div>
    </div>
    <div class="summary-card">
      <div class="value">{{funds_screened}}</div>
      <div class="label">筛选基金</div>
    </div>
    <div class="summary-card">
      <div class="value">{{funds_qualified}}</div>
      <div class="label">达标推荐</div>
    </div>
    <div class="summary-card">
      <div class="value">{{avg_wr7}}%</div>
      <div class="label">Top平均7天胜率</div>
    </div>
  </div>

  <!-- Hot Boards -->
  <div class="section">
    <h2>🔥 热门板块</h2>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>排名</th><th>板块</th><th>今日涨幅</th><th>主力流入%</th>
          <th>综合分</th><th>达标基金</th>
        </tr></thead>
        <tbody>
          {{boards_rows}}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Recommendations -->
  <div class="section">
    <h2>🎯 推荐基金</h2>
    {{fund_cards}}
  </div>

  <div class="footer">
    <p>数据来源: 东方财富 / 天天基金 | 回测方法: 滚动窗口胜率统计</p>
    <p>历史胜率不代表未来收益。C类基金持有不足7天将收取1.5%惩罚费。</p>
    <p><a href="https://github.com/JivonKiang/alipay-quant-system">GitHub 仓库</a></p>
  </div>
</div>
</body>
</html>
"""


def generate_boards_rows(boards: list) -> str:
    rows = []
    for i, b in enumerate(boards):
        chg_cls = "pos" if b.get("change_pct", 0) > 0 else "neg"
        chg_sign = "+" if b.get("change_pct", 0) > 0 else ""
        rows.append(
            f"<tr>"
            f"<td>{i+1}</td>"
            f"<td><strong>{b['name']}</strong></td>"
            f'<td class="num {chg_cls}">{chg_sign}{b.get("change_pct", 0):.2f}%</td>'
            f'<td class="num">{b.get("main_flow_pct", 0):+.2f}%</td>'
            f'<td class="num">{b.get("score", 0):.1f}</td>'
            f'<td>{b.get("funds_qualified", 0)}/{b.get("funds_found", 0)}</td>'
            f"</tr>"
        )
    return "\n".join(rows)


def generate_fund_cards(recommendations: list) -> str:
    cards = []
    for rec in recommendations:
        wr7 = rec.get("win_rate_7d", {})
        wr14 = rec.get("win_rate_14d", {})
        wr30 = rec.get("win_rate_30d", {})

        reasons_html = "\n".join(f"<li>{r}</li>" for r in rec.get("reasons", []))
        risks_html = "\n".join(f"<li>{r}</li>" for r in rec.get("risks", []))

        # 板块涨跌颜色
        board_chg = rec.get("board_change_pct", 0)
        board_chg_cls = "pos" if board_chg > 0 else "neg"
        board_chg_sign = "+" if board_chg > 0 else ""

        card = f"""
<div class="fund-card">
  <div class="fund-header">
    <div>
      <div class="fund-title">
        #{rec['rank']} {rec['fund_name']}
        <span class="fund-code">{rec['fund_code']}</span>
      </div>
      <div class="fund-board">
        板块: <strong>{rec['board_name']}</strong>
        (今日<span class="{board_chg_cls}">{board_chg_sign}{board_chg:.2f}%</span>)
        | 数据周期: {rec['data_days']}天
      </div>
    </div>
    <div>
      <div class="fund-score">{rec['total_score']:.1f}</div>
      <div class="fund-score-label">综合评分</div>
    </div>
  </div>

  <div class="metrics-grid">
    <div class="metric">
      <div class="value">{wr7.get('win_rate', 0)}%</div>
      <div class="label">7天胜率<br/>({wr7.get('samples', 0)}窗口)</div>
    </div>
    <div class="metric">
      <div class="value">{wr14.get('win_rate', 0)}%</div>
      <div class="label">14天胜率<br/>({wr14.get('samples', 0)}窗口)</div>
    </div>
    <div class="metric">
      <div class="value">{wr30.get('win_rate', 0)}%</div>
      <div class="label">30天胜率<br/>({wr30.get('samples', 0)}窗口)</div>
    </div>
    <div class="metric">
      <div class="value">{rec.get('annual_return_pct', 0)}%</div>
      <div class="label">年化收益</div>
    </div>
    <div class="metric">
      <div class="value">{rec.get('max_drawdown_pct', 0)}%</div>
      <div class="label">最大回撤</div>
    </div>
    <div class="metric">
      <div class="value">{rec.get('sharpe_ratio', 0)}</div>
      <div class="label">夏普比率</div>
    </div>
    <div class="metric">
      <div class="value">{rec.get('annual_volatility_pct', 0)}%</div>
      <div class="label">年化波动</div>
    </div>
    <div class="metric">
      <div class="value">{rec.get('recent_20d_pct', 0):+.2f}%</div>
      <div class="label">近20日收益</div>
    </div>
  </div>

  <div class="reasons">
    <h4>✅ 推荐理由</h4>
    <ul>{reasons_html}</ul>
  </div>

  <div class="risks">
    <h4>⚠️ 风险提示</h4>
    <ul>{risks_html}</ul>
  </div>

  <div class="fee-banner">
    💰 C类基金: 锁定{rec.get('fee_lock_days', 7)}天 | 持有不足7天将收取1.5%惩罚费
  </div>
</div>
"""
        cards.append(card)

    if not cards:
        return '<div style="text-align:center;padding:2rem;color:var(--muted);">当前无达标基金推荐（所有基金胜率未达过滤阈值）</div>'

    return "\n".join(cards)


def generate(report_path: str, output_path: str):
    """从 JSON 报告生成 HTML"""
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    if "error" in report:
        html = HTML_TEMPLATE.replace("{{report_time}}", report.get("report_time", ""))
        html = html.replace("{{boards_count}}", "0")
        html = html.replace("{{funds_screened}}", "0")
        html = html.replace("{{funds_qualified}}", "0")
        html = html.replace("{{avg_wr7}}", "0")
        html = html.replace("{{boards_rows}}", "")
        html = html.replace("{{fund_cards}}", f'<div style="text-align:center;padding:2rem;color:#ef4444;">错误: {report["error"]}</div>')
    else:
        s = report.get("summary", {})
        avg_wr7 = s.get("avg_wr7_top", 0)

        html = HTML_TEMPLATE.replace("{{report_time}}", report.get("report_time", ""))
        html = html.replace("{{boards_count}}", str(s.get("total_boards_scanned", 0)))
        html = html.replace("{{funds_screened}}", str(s.get("total_funds_screened", 0)))
        html = html.replace("{{funds_qualified}}", str(s.get("total_qualified", 0)))
        html = html.replace("{{avg_wr7}}", str(avg_wr7))
        html = html.replace("{{boards_rows}}", generate_boards_rows(report.get("hot_boards", [])))
        html = html.replace("{{fund_cards}}", generate_fund_cards(report.get("recommendations", [])))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML 报告已生成: {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="output/recommendation.json", help="JSON 报告路径")
    parser.add_argument("--output", default="output/index.html", help="HTML 输出路径")
    args = parser.parse_args()
    generate(args.input, args.output)
