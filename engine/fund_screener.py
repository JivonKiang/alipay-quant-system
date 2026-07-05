"""
Fund Screener — C类基金筛选器
根据板块主题筛选对应的C类基金，按历史收益+回撤+规模综合排名
"""
import json
import re
import time
import math
import urllib.request
from datetime import datetime
from typing import List, Dict, Optional


class FundScreener:
    """C类基金筛选器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.headers = {
            "Referer": "https://fund.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # 板块→关键词映射 (用于基金名称匹配)
        self.board_keywords = {
            "半导体": ["半导体", "芯片", "集成电路"],
            "芯片": ["芯片", "半导体", "集成电路"],
            "存储芯片": ["存储", "闪存", "内存"],
            "PCB": ["PCB", "印制电路"],
            "CPO": ["CPO", "光模块", "光引擎"],
            "AI算力": ["算力", "AI", "人工智能", "数字经济"],
            "消费电子": ["消费电子"],
            "光刻胶": ["光刻胶", "光刻"],
            "汽车芯片": ["汽车芯片", "车规", "汽车电子"],
            "第三代半导体": ["第三代半导体", "碳化硅", "氮化镓"],
            "卫星通信": ["卫星", "航天", "通信"],
            "AIGC": ["AIGC", "人工智能", "AI"],
            "华为": ["华为"],
            "苹果": ["苹果"],
            "锂电池": ["锂电", "电池", "新能源"],
            "光伏": ["光伏", "太阳能"],
            "风电": ["风电", "风力发电"],
            "新能源车": ["新能源车", "新能源汽车", "电动车"],
            "机器人": ["机器人", "自动化"],
            "军工": ["军工", "国防"],
            "创新药": ["创新药", "生物医药"],
            "中药": ["中药"],
            "证券": ["证券", "券商"],
            "稀土": ["稀土"],
            "铜": ["铜", "有色金属"],
            "黄金": ["黄金", "贵金属"],
        }

    def _fetch_json(self, url: str) -> Dict:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    def _fetch_text(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")

    def fetch_fund_list(self) -> List[Dict]:
        """
        获取全量基金列表
        返回: [{code, name, type}, ...]
        """
        try:
            url = "http://fund.eastmoney.com/js/fundcode_search.js"
            text = self._fetch_text(url)
            # 提取 JS 数组
            match = re.search(r'var r = \[(.+)\]', text, re.DOTALL)
            if not match:
                return []
            # 解析每条记录: ["代码","名称","类型","拼音","成立日期"]
            records_str = f"[{match.group(1)}]"
            records = json.loads(records_str)
            return [
                {"code": r[0], "name": r[2] if len(r) > 2 else r[1], "type": r[1] if len(r) > 2 else ""}
                for r in records
            ]
        except Exception as e:
            print(f"[WARN] 基金列表获取失败: {e}")
            return []

    def find_c_funds_by_board(self, board_name: str, fund_list: List[Dict] = None) -> List[Dict]:
        """
        根据板块名称筛选对应的C类基金
        匹配逻辑:
          1. 基金名称以"C"结尾 (不含"C类"中间字符)
          2. 基金名称包含板块相关关键词
          3. 排除ETF、LOF、联接基金(除非明确含C)
        """
        if not fund_list:
            fund_list = self.fetch_fund_list()

        keywords = self.board_keywords.get(board_name, [board_name])
        c_funds = []

        for f in fund_list:
            name = f.get("name", "")
            code = f.get("code", "")

            # C类识别: 名称以"C"结尾，或名称包含"C类"
            if not (name.endswith("C") or "C类" in name or name.endswith("c")):
                continue

            # 关键词匹配
            matched_keyword = ""
            for kw in keywords:
                if kw in name:
                    matched_keyword = kw
                    break
            if not matched_keyword:
                continue

            # 排除货币基金和债券基金 (只保留股票型/混合型)
            if any(x in name for x in ["货币", "理财", "短债", "同业存单"]):
                continue

            c_funds.append({
                "code": code,
                "name": name,
                "matched_keyword": matched_keyword,
            })

        return c_funds

    def fetch_fund_nav_history(self, fund_code: str, days: int = 365) -> List[Dict]:
        """
        获取基金历史净值 (用于回测分析)
        返回: [{date, nav, daily_change_pct}, ...]
        """
        try:
            url = (
                f"https://api.fund.eastmoney.com/f10/lsjz?"
                f"fundCode={fund_code}&pageIndex=1&pageSize={days}"
            )
            data = self._fetch_json(url)
            records = data.get("Data", {}).get("LSJZList", [])
            return [
                {
                    "date": r.get("LSJZRQ", r.get("FSRQ", "")),
                    "nav": float(r.get("DWJZ", 0)),
                    "daily_change_pct": float(r.get("JZZZL", 0)) if r.get("JZZZL") else 0,
                }
                for r in records if r.get("DWJZ", 0)
            ]
        except Exception as e:
            return []

    def analyze_fund_history(self, nav_data: List[Dict]) -> Dict:
        """
        分析基金历史数据，计算关键指标
        返回: 7天/14天/30天胜率、最大回撤、年化收益、波动率、夏普比率
        """
        if len(nav_data) < 30:
            return {"error": "数据不足30天"}

        # 按日期正序
        data = sorted(nav_data, key=lambda x: x["date"])
        navs = [d["nav"] for d in data]
        n = len(navs)

        # ---- 滚动窗口胜率分析 ----
        def calc_win_rate(window: int) -> Dict:
            wins = 0
            total = 0
            returns = []
            for i in range(window, n):
                ret = (navs[i] - navs[i - window]) / navs[i - window] * 100
                returns.append(ret)
                total += 1
                if ret > 0:
                    wins += 1
            if total == 0:
                return {"win_rate": 0, "avg_return": 0, "median_return": 0, "samples": 0}
            returns_sorted = sorted(returns)
            median = returns_sorted[len(returns_sorted) // 2]
            return {
                "win_rate": round(wins / total * 100, 1),
                "avg_return": round(sum(returns) / len(returns), 2),
                "median_return": round(median, 2),
                "samples": total,
            }

        wr_7d = calc_win_rate(7)
        wr_14d = calc_win_rate(14)
        wr_30d = calc_win_rate(30)

        # ---- 最大回撤 ----
        peak = navs[0]
        max_dd = 0
        for nav in navs[1:]:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # ---- 年化收益 ----
        if n > 1:
            total_return = (navs[-1] - navs[0]) / navs[0]
            annual_return = (1 + total_return) ** (252 / n) - 1
        else:
            annual_return = 0

        # ---- 日波动率 ----
        daily_changes = [d["daily_change_pct"] for d in data if d["daily_change_pct"] != 0]
        if len(daily_changes) >= 2:
            avg_chg = sum(daily_changes) / len(daily_changes)
            variance = sum((c - avg_chg) ** 2 for c in daily_changes) / len(daily_changes)
            daily_vol = math.sqrt(variance)
            annual_vol = daily_vol * math.sqrt(252)
        else:
            annual_vol = 0

        # ---- 夏普比率 (无风险利率2.5%) ----
        rf = 0.025
        sharpe = (annual_return - rf) / (annual_vol / 100) if annual_vol > 0 else 0

        # ---- 近期趋势 (近5/10/20日收益) ----
        def recent_return(days: int) -> float:
            if n > days:
                return round((navs[-1] - navs[-1 - days]) / navs[-1 - days] * 100, 2)
            return 0

        return {
            "data_days": n,
            "latest_nav": navs[-1],
            "max_drawdown_pct": round(max_dd, 2),
            "annual_return_pct": round(annual_return * 100, 2),
            "annual_volatility_pct": round(annual_vol, 2),
            "sharpe_ratio": round(sharpe, 2),
            "recent_5d_pct": recent_return(5),
            "recent_10d_pct": recent_return(10),
            "recent_20d_pct": recent_return(20),
            "win_rate_7d": wr_7d,
            "win_rate_14d": wr_14d,
            "win_rate_30d": wr_30d,
        }

    def score_funds(self, funds: List[Dict], nav_data_map: Dict[str, List[Dict]] = None) -> List[Dict]:
        """
        综合评分排名
        评分因子:
          - 7天持有胜率: 30%
          - 14天持有胜率: 20%
          - 年化收益: 20%
          - 最大回撤(越小越好): 15%
          - 夏普比率: 10%
          - 近期趋势(近20日): 5%
        """
        scored = []
        for f in funds:
            code = f["code"]
            if nav_data_map and code in nav_data_map:
                nav_data = nav_data_map[code]
            else:
                print(f"   获取 {code} {f['name']} 历史数据...")
                nav_data = self.fetch_fund_nav_history(code, 365)
                time.sleep(0.3)

            analysis = self.analyze_fund_history(nav_data)
            if "error" in analysis:
                continue

            # 评分计算
            wr7 = analysis["win_rate_7d"]["win_rate"]     # 7天胜率
            wr14 = analysis["win_rate_14d"]["win_rate"]    # 14天胜率
            ann_ret = analysis["annual_return_pct"]         # 年化收益
            max_dd = analysis["max_drawdown_pct"]           # 最大回撤
            sharpe = analysis["sharpe_ratio"]               # 夏普
            ret_20d = analysis["recent_20d_pct"]            # 近20日收益

            score_wr7 = min(100, wr7)                       # 胜率直接映射
            score_wr14 = min(100, wr14)
            score_ret = min(100, max(0, 50 + ann_ret * 5))  # 年化10%=100
            score_dd = max(0, 100 - max_dd * 2)              # 回撤10%=80
            score_sharpe = min(100, max(0, 50 + sharpe * 20))  # 夏普2.5=100
            score_trend = min(100, max(0, 50 + ret_20d * 3))  # 近20日涨5%=65

            total = (
                score_wr7 * 0.30 +
                score_wr14 * 0.20 +
                score_ret * 0.20 +
                score_dd * 0.15 +
                score_sharpe * 0.10 +
                score_trend * 0.05
            )

            scored.append({
                **f,
                "analysis": analysis,
                "scores": {
                    "wr7_score": round(score_wr7, 1),
                    "wr14_score": round(score_wr14, 1),
                    "return_score": round(score_ret, 1),
                    "drawdown_score": round(score_dd, 1),
                    "sharpe_score": round(score_sharpe, 1),
                    "trend_score": round(score_trend, 1),
                    "total": round(total, 1),
                },
            })

        scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
        return scored

    def screen(self, board_name: str, top_n: int = 5, fund_list: List[Dict] = None) -> List[Dict]:
        """
        完整筛选: 板块→找C类基金→获取数据→评分→Top N
        """
        print(f"🔍 筛选 [{board_name}] 相关C类基金...")
        if not fund_list:
            fund_list = self.fetch_fund_list()
        c_funds = self.find_c_funds_by_board(board_name, fund_list)
        if not c_funds:
            print(f"   未找到 [{board_name}] 相关C类基金")
            return []

        print(f"   找到 {len(c_funds)} 只C类基金，开始评分...")
        scored = self.score_funds(c_funds)
        top = scored[:top_n]
        print(f"✅ [{board_name}] 筛选完成，Top {top_n} 基金:")
        for f in top:
            a = f["analysis"]
            print(f"   {f['code']} {f['name']}: "
                  f"7天胜率{a['win_rate_7d']['win_rate']}%, "
                  f"14天胜率{a['win_rate_14d']['win_rate']}%, "
                  f"年化{a['annual_return_pct']}%, "
                  f"最大回撤{a['max_drawdown_pct']}%, "
                  f"夏普{a['sharpe_ratio']}")
        return top


from typing import Dict
