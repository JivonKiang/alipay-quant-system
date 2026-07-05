"""
Fund Screener — C类基金筛选器 (多渠道版)
根据板块主题筛选对应的C类基金，按历史收益+回撤+规模综合排名

数据渠道:
  1. 天天基金搜索API (fundsuggest.eastmoney.com) — 关键词精准搜索
  2. 主题基金API (fundtest.eastmoney.com) — 板块→主题→基金映射
  3. 全量基金列表 (fundcode_search.js) — 广泛名称匹配 (兜底)
  4. 蛋卷基金 (danjuanapp.com) — 第三方交叉验证
"""
import json
import re
import time
import math
from datetime import datetime
from typing import List, Dict, Optional, Set


class FundScreener:
    """C类基金筛选器 (多渠道)"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.headers_em = {
            "Referer": "https://fund.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        self.headers_dj = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        # 扩展关键词映射表: 板块→所有相关关键词 (同义词/上下游/别名)
        self.board_keywords = {
            "半导体": ["半导体", "芯片", "集成电路", "半导体芯片", "科创芯片"],
            "芯片": ["芯片", "半导体", "集成电路", "科创芯片", "中证芯片"],
            "存储芯片": ["存储", "闪存", "内存", "存储芯片"],
            "PCB": ["PCB", "印制电路", "电路板"],
            "CPO": ["CPO", "光模块", "光引擎", "共封装光学"],
            "光模块": ["光模块", "CPO", "光通信"],
            "AI算力": ["算力", "人工智能", "AI", "数字经济", "智能", "AIGC",
                       "ChatGPT", "大模型", "深度学习", "机器学习", "云计算"],
            "消费电子": ["消费电子", "智能穿戴", "TWS", "耳机", "AR", "VR", "MR"],
            "光刻胶": ["光刻胶", "光刻", "半导体材料"],
            "汽车芯片": ["汽车芯片", "车规", "汽车电子", "智能驾驶", "自动驾驶", "车用"],
            "第三代半导体": ["第三代半导体", "碳化硅", "氮化镓", "宽禁带"],
            "卫星通信": ["卫星", "航天", "卫星通信", "商业航天", "北斗", "空间站"],
            "AIGC": ["AIGC", "人工智能", "AI", "大模型", "生成式"],
            "华为": ["华为", "鸿蒙", "华为概念", "欧拉", "昇腾", "海思"],
            "苹果": ["苹果", "Apple", "iPhone", "果链"],
            "锂电池": ["锂电", "电池", "新能源", "动力电池", "储能", "宁德", "比亚迪"],
            "光伏": ["光伏", "太阳能", "光伏产业", "硅料", "组件"],
            "风电": ["风电", "风力发电", "海上风电", "风能"],
            "新能源车": ["新能源车", "新能源汽车", "电动车", "智能汽车", "整车"],
            "机器人": ["机器人", "自动化", "人形机器人", "减速器", "伺服", "机器视觉",
                       "谐波减速器", "RV减速器", "滚珠丝杠", "传感器"],
            "减速器": ["减速器", "谐波减速器", "RV减速器", "精密传动", "传动"],
            "军工": ["军工", "国防", "军工装备", "航空", "航天", "船舶", "兵器"],
            "创新药": ["创新药", "生物医药", "医药", "CRO", "CXO"],
            "中药": ["中药", "中成药", "中医药"],
            "证券": ["证券", "券商", "金融", "资本市场"],
            "稀土": ["稀土", "稀土永磁"],
            "铜": ["铜", "有色金属", "矿业"],
            "黄金": ["黄金", "贵金属", "金"],
            "船舶": ["船舶", "造船", "航运", "中船"],
            "汽车热管理": ["热管理", "汽车热管理", "热泵", "散热"],
            "轮毂电机": ["轮毂电机", "电机", "驱动电机"],
            "金融科技": ["金融科技", " fintech", "数字货币", "区块链", "银行IT"],
            "房地产": ["房地产", "地产", "物业"],
            "白酒": ["白酒", "食品饮料", "酒"],
            "医药": ["医药", "医疗", "生物", "健康", "医美", "中药", "创新药", "CRO"],
            "银行": ["银行", "商业银行"],
            "保险": ["保险"],
            "碳中和": ["碳中和", "碳交易", "环保", "节能"],
            "5G": ["5G", "通信", "5G通信", "通信设备"],
            "物联网": ["物联网", "IoT", "智能家居", "智慧城市"],
            "数据要素": ["数据要素", "数据", "大数据", "数据中心", "IDC"],
        }
        # 全量基金列表缓存
        self._fund_list_cache: Optional[List[Dict]] = None

    def _fetch(self, url: str, headers: Dict = None) -> str:
        """通用请求 (requests优先, urllib兜底)"""
        headers = headers or self.headers_em
        try:
            import requests
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception:
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, headers: Dict = None) -> Dict:
        text = self._fetch(url, headers)
        return json.loads(text)

    # ================================================================
    # 渠道1: 天天基金搜索API — 关键词精准搜索
    # ================================================================
    def search_fund_by_keyword(self, keyword: str) -> List[Dict]:
        """
        使用天天基金搜索API按关键词搜索基金
        接口: fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx
        """
        try:
            url = f"http://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?m=1&key={keyword}"
            text = self._fetch(url, self.headers_em)
            # 返回可能是JSON或JSONP
            if text.startswith("jQuery"):
                text = re.search(r'\((.+)\)', text)
                if text:
                    text = text.group(1)
            data = json.loads(text)
            items = data.get("Datas", []) or data.get("Data", []) or data.get("datas", [])
            results = []
            for item in items:
                code = item.get("CODE", item.get("Code", item.get("code", "")))
                name = item.get("NAME", item.get("Name", item.get("name", "")))
                if code and name:
                    results.append({"code": code, "name": name, "source": "search_api"})
            return results
        except Exception as e:
            return []

    # ================================================================
    # 渠道2: 主题基金API — 板块→主题→基金
    # ================================================================
    def fetch_topic_funds(self, topic_code: str) -> List[Dict]:
        """
        使用天天基金主题基金API获取某主题下的基金列表
        接口: fundtest.eastmoney.com/dataapi1015/ztjj/GetBKRelTopicFund
        """
        try:
            ts = int(time.time() * 1000)
            url = (
                f"http://fundtest.eastmoney.com/dataapi1015/ztjj/GetBKRelTopicFund"
                f"?callback=jQuery&sort=SON_1N&sorttype=DESC&pageindex=1&pagesize=50"
                f"&tp={topic_code}&isbuy=1&_={ts}"
            )
            text = self._fetch(url, self.headers_em)
            # JSONP
            match = re.search(r'jQuery\((.+)\)', text)
            if not match:
                return []
            data = json.loads(match.group(1))
            items = data.get("Data", {}).get("Datas", []) or data.get("Data", [])
            results = []
            for item in items:
                code = item.get("FCODE", "")
                name = item.get("SHORTNAME", item.get("NAME", ""))
                if code and name:
                    results.append({
                        "code": code,
                        "name": name,
                        "source": "topic_api",
                        "return_1y": item.get("SON_1N", 0),
                    })
            return results
        except Exception as e:
            return []

    def fetch_topic_list(self) -> Dict[str, str]:
        """获取全部主题分类 (行业+概念)，返回 {主题名: 主题代码}"""
        try:
            ts = int(time.time() * 1000)
            url = f"http://fundtest.eastmoney.com/dataapi1015/ztjj/GetBKListByBKType?callback=jQuery&_={ts}"
            text = self._fetch(url, self.headers_em)
            match = re.search(r'jQuery\((.+)\)', text)
            if not match:
                return {}
            data = json.loads(match.group(1))
            topics = {}
            # 行业分类
            for item in data.get("Data", {}).get("hy", []):
                topics[item.get("BKName", "")] = item.get("BKCode", "")
            # 概念分类
            for item in data.get("Data", {}).get("gn", []):
                topics[item.get("BKName", "")] = item.get("BKCode", "")
            return topics
        except Exception:
            return {}

    # ================================================================
    # 渠道3: 全量基金列表 — 广泛名称匹配 (兜底)
    # ================================================================
    def fetch_fund_list(self) -> List[Dict]:
        """获取全量基金列表"""
        if self._fund_list_cache:
            return self._fund_list_cache
        try:
            url = "http://fund.eastmoney.com/js/fundcode_search.js"
            text = self._fetch(url, self.headers_em)
            match = re.search(r'var r = \[(.+)\]', text, re.DOTALL)
            if not match:
                return []
            records = json.loads(f"[{match.group(1)}]")
            self._fund_list_cache = [
                {"code": r[0], "name": r[2] if len(r) > 2 else r[1], "type": r[1] if len(r) > 2 else ""}
                for r in records
            ]
            return self._fund_list_cache
        except Exception as e:
            print(f"[WARN] 基金列表获取失败: {e}")
            return []

    # ================================================================
    # 渠道4: 蛋卷基金 — 第三方交叉验证
    # ================================================================
    def search_danjuan(self, keyword: str) -> List[Dict]:
        """蛋卷基金搜索"""
        try:
            import urllib.parse
            kw = urllib.parse.quote(keyword)
            url = f"https://danjuanapp.com/djapi/search/v2/fund?keyword={kw}&size=20"
            text = self._fetch(url, self.headers_dj)
            data = json.loads(text)
            items = data.get("data", {}).get("items", [])
            results = []
            for item in items:
                code = item.get("fd_code", "")
                name = item.get("fd_name", "")
                if code and name:
                    results.append({"code": code, "name": name, "source": "danjuan"})
            return results
        except Exception:
            return []

    # ================================================================
    # C类识别 + 过滤
    # ================================================================
    @staticmethod
    def is_c_class_fund(name: str) -> bool:
        """判断是否为C类基金"""
        if not name:
            return False
        # 名称以C结尾 (不是"AC"或"BC"这种多份额缩写)
        if name.endswith("C") and not name.endswith("AC") and not name.endswith("BC") and not name.endswith("EC") and not name.endswith("HC"):
            return True
        # 名称包含"C类"
        if "C类" in name:
            return True
        return False

    @staticmethod
    def is_excluded(name: str) -> bool:
        """排除不可投资的基金类型"""
        exclude_words = ["货币", "理财", "短债", "同业存单", "理财型", "理财宝"]
        return any(x in name for x in exclude_words)

    # ================================================================
    # 核心方法: 多渠道搜索C类基金
    # ================================================================
    def find_c_funds_by_board(self, board_name: str, fund_list: List[Dict] = None) -> List[Dict]:
        """
        多渠道搜索板块对应的C类基金
        顺序:
          1. 天天基金搜索API (关键词精准)
          2. 主题基金API (板块映射)
          3. 全量基金列表名称匹配 (兜底)
          4. 蛋卷基金搜索 (交叉验证)
        """
        keywords = self.board_keywords.get(board_name, [board_name])
        all_funds: Dict[str, Dict] = {}  # code -> fund (去重)

        # ---- 渠道1: 搜索API ----
        for kw in keywords:
            try:
                results = self.search_fund_by_keyword(kw)
                for f in results:
                    if self.is_c_class_fund(f["name"]) and not self.is_excluded(f["name"]):
                        all_funds[f["code"]] = {**f, "matched_keyword": kw}
                time.sleep(0.2)
            except Exception:
                pass

        print(f"   渠道1(搜索API): 找到 {len(all_funds)} 只候选")

        # ---- 渠道2: 主题基金API ----
        try:
            topic_map = self.fetch_topic_list()
            # 按关键词匹配主题
            for kw in keywords:
                for topic_name, topic_code in topic_map.items():
                    if kw in topic_name or topic_name in board_name:
                        topic_funds = self.fetch_topic_funds(topic_code)
                        for f in topic_funds:
                            if self.is_c_class_fund(f["name"]) and not self.is_excluded(f["name"]):
                                if f["code"] not in all_funds:
                                    all_funds[f["code"]] = {**f, "matched_keyword": topic_name}
                        time.sleep(0.3)
        except Exception as e:
            print(f"   渠道2(主题API): 失败 {e}")

        print(f"   渠道1+2: 找到 {len(all_funds)} 只候选")

        # ---- 渠道3: 全量基金列表匹配 ----
        if not fund_list:
            fund_list = self.fetch_fund_list()
        for f in fund_list:
            name = f.get("name", "")
            code = f.get("code", "")
            if code in all_funds:
                continue  # 已有
            if not self.is_c_class_fund(name):
                continue
            if self.is_excluded(name):
                continue
            for kw in keywords:
                if kw in name:
                    all_funds[code] = {**f, "source": "full_list", "matched_keyword": kw}
                    break

        print(f"   渠道1+2+3: 找到 {len(all_funds)} 只候选")

        # ---- 渠道4: 蛋卷基金 (补充) ----
        for kw in keywords:
            try:
                dj_results = self.search_danjuan(kw)
                for f in dj_results:
                    if self.is_c_class_fund(f["name"]) and not self.is_excluded(f["name"]):
                        if f["code"] not in all_funds:
                            all_funds[f["code"]] = {**f, "matched_keyword": kw}
                time.sleep(0.3)
            except Exception:
                pass

        print(f"   全渠道合计: {len(all_funds)} 只C类基金")

        return list(all_funds.values())

    def fetch_fund_nav_history(self, fund_code: str, days: int = 365) -> List[Dict]:
        """获取基金历史净值 (用于回测分析)"""
        try:
            url = (
                f"https://api.fund.eastmoney.com/f10/lsjz?"
                f"fundCode={fund_code}&pageIndex=1&pageSize={days}"
            )
            data = self._fetch_json(url, self.headers_em)
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

        data = sorted(nav_data, key=lambda x: x["date"])
        navs = [d["nav"] for d in data]
        n = len(navs)

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

        peak = navs[0]
        max_dd = 0
        for nav in navs[1:]:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak * 100
            if dd > max_dd:
                max_dd = dd

        if n > 1:
            total_return = (navs[-1] - navs[0]) / navs[0]
            annual_return = (1 + total_return) ** (252 / n) - 1
        else:
            annual_return = 0

        daily_changes = [d["daily_change_pct"] for d in data if d["daily_change_pct"] != 0]
        if len(daily_changes) >= 2:
            avg_chg = sum(daily_changes) / len(daily_changes)
            variance = sum((c - avg_chg) ** 2 for c in daily_changes) / len(daily_changes)
            annual_vol = math.sqrt(variance) * math.sqrt(252)
        else:
            annual_vol = 0

        rf = 0.025
        sharpe = (annual_return - rf) / (annual_vol / 100) if annual_vol > 0 else 0

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
        """综合评分排名"""
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

            wr7 = analysis["win_rate_7d"]["win_rate"]
            wr14 = analysis["win_rate_14d"]["win_rate"]
            ann_ret = analysis["annual_return_pct"]
            max_dd = analysis["max_drawdown_pct"]
            sharpe = analysis["sharpe_ratio"]
            ret_20d = analysis["recent_20d_pct"]

            score_wr7 = min(100, wr7)
            score_wr14 = min(100, wr14)
            score_ret = min(100, max(0, 50 + ann_ret * 5))
            score_dd = max(0, 100 - max_dd * 2)
            score_sharpe = min(100, max(0, 50 + sharpe * 20))
            score_trend = min(100, max(0, 50 + ret_20d * 3))

            total = (
                score_wr7 * 0.30 + score_wr14 * 0.20 +
                score_ret * 0.20 + score_dd * 0.15 +
                score_sharpe * 0.10 + score_trend * 0.05
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
        """完整筛选: 板块→多渠道找C类基金→获取数据→评分→Top N"""
        print(f"🔍 多渠道筛选 [{board_name}] 相关C类基金...")
        c_funds = self.find_c_funds_by_board(board_name, fund_list)
        if not c_funds:
            print(f"   未找到 [{board_name}] 相关C类基金")
            return []

        print(f"   开始评分...")
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
