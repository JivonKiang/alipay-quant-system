"""
Board Scanner — 板块热度扫描器
扫描全部行业板块+概念板块，按多因子打分排名
因子: 涨幅 + 主力净流入 + 资金流向 + 连续性 + 领涨股强度
"""
import json
import time
import math
from datetime import datetime
from typing import List, Dict, Tuple


class BoardScanner:
    """板块热度扫描器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.headers = {
            "Referer": "https://quote.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        self.base_url = "https://push2.eastmoney.com/api/qt/clist/get"
        self.kline_url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    def _fetch_json(self, url: str) -> Dict:
        try:
            import requests
            resp = requests.get(url, headers=self.headers, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            # fallback to urllib
            import urllib.request
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())

    def fetch_all_boards(self, board_type: str = "concept") -> List[Dict]:
        """
        获取全部板块数据
        board_type: "concept"(概念板块) / "industry"(行业板块)
        返回: [{code, name, change_pct, main_flow, main_flow_pct,
                leader_code, leader_name, leader_change, up_count}, ...]
        """
        fs_map = {
            "concept": "m:90+t:3",
            "industry": "m:90+t:2",
        }
        fs = fs_map.get(board_type, fs_map["concept"])

        all_boards = []
        page = 1
        while True:
            url = (
                f"{self.base_url}?"
                f"fid=f3&po=1&pz=100&pn={page}&np=1&fltt=2&invt=2&"
                f"fs={fs}&fields=f3,f12,f14,f62,f66,f69,f72,f75,f78,f81,f84,f87,f124,f184,f204,f205"
                f"&_={int(time.time()*1000)}"
            )
            try:
                data = self._fetch_json(url)
                diff = data.get("data", {}).get("diff", [])
                if not diff:
                    break
                for d in diff:
                    main_flow = d.get("f62", 0) or 0
                    main_flow_pct = d.get("f184", 0) or 0
                    all_boards.append({
                        "code": f"90.BK{d.get('f12', '')}",
                        "name": d.get("f14", ""),
                        "change_pct": round(d.get("f3", 0), 2),
                        "main_flow": main_flow,           # 主力净流入(元)
                        "main_flow_pct": round(main_flow_pct, 2),  # 主力净流入占比%
                        "leader_name": d.get("f205", ""),   # 领涨股
                        "up_count": d.get("f124", 0) or 0,  # 上涨家数
                    })
                total = data.get("data", {}).get("total", 0)
                if len(all_boards) >= total:
                    break
                page += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"[WARN] 板块扫描失败(p{page}): {e}")
                break

        return all_boards

    def fetch_board_kline(self, board_code: str, days: int = 20) -> List[Dict]:
        """获取板块近期K线用于连续性分析"""
        url = (
            f"{self.kline_url}?"
            f"secid={board_code}&fields1=f1,f2,f3,f4,f5,f6&"
            f"fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=0&"
            f"end=20500101&lmt={days}"
        )
        try:
            data = self._fetch_json(url)
            klines = data.get("data", {}).get("klines", [])
            result = []
            for k in klines:
                parts = k.split(",")
                if len(parts) >= 7:
                    result.append({
                        "date": parts[0],
                        "close": float(parts[1]),
                        "high": float(parts[2]),
                        "low": float(parts[3]),
                        "volume": int(parts[5]),
                        "change_pct": float(parts[8]) if len(parts) > 8 else 0,
                    })
            return result
        except Exception as e:
            return []

    def analyze_continuity(self, klines: List[Dict]) -> Dict:
        """
        分析板块K线连续性
        返回: {consecutive_up, consecutive_down, avg_change_5d, volatility}
        """
        if len(klines) < 2:
            return {"consecutive_up": 0, "consecutive_down": 0, "avg_change_5d": 0, "volatility": 0}

        # 连续上涨/下跌天数
        consec_up = 0
        consec_down = 0
        for k in reversed(klines):
            if k.get("change_pct", 0) > 0:
                consec_up += 1
            else:
                break
        for k in reversed(klines):
            if k.get("change_pct", 0) < 0:
                consec_down += 1
            else:
                break

        # 近5日平均涨跌幅
        recent_5 = klines[-5:] if len(klines) >= 5 else klines
        avg_5d = sum(k.get("change_pct", 0) for k in recent_5) / len(recent_5)

        # 近5日波动率
        changes = [k.get("change_pct", 0) for k in recent_5]
        if len(changes) >= 2:
            avg_c = sum(changes) / len(changes)
            variance = sum((c - avg_c) ** 2 for c in changes) / len(changes)
            volatility = math.sqrt(variance)
        else:
            volatility = 0

        return {
            "consecutive_up": consec_up,
            "consecutive_down": consec_down,
            "avg_change_5d": round(avg_5d, 2),
            "volatility": round(volatility, 2),
        }

    def score_boards(self, boards: List[Dict]) -> List[Dict]:
        """
        多因子打分排名
        因子权重:
          - 今日涨幅: 25%
          - 主力净流入: 30%
          - 近5日连续性: 20%
          - 板块上涨家数比: 15%
          - 波动率(低波动加分): 10%
        """
        scored = []
        for b in boards:
            # 1. 涨幅得分 (0-100)
            chg = b.get("change_pct", 0)
            score_chg = min(100, max(0, 50 + chg * 10))  # 涨1%=60分

            # 2. 主力净流入得分 (0-100)
            flow_pct = b.get("main_flow_pct", 0)
            score_flow = min(100, max(0, 50 + flow_pct * 10))  # 1%=60分

            # 3. 连续性得分 (需要K线)
            klines = self.fetch_board_kline(b["code"], 10)
            cont = self.analyze_continuity(klines)
            consec = cont.get("consecutive_up", 0)
            score_cont = min(100, consec * 25)  # 连涨4天=100

            # 4. 近5日均值 (正得分,负扣分)
            avg_5d = cont.get("avg_change_5d", 0)
            score_avg5 = min(100, max(0, 50 + avg_5d * 15))

            # 5. 波动率 (低波动=稳定趋势,加分; 高波动=不确定,扣分)
            vol = cont.get("volatility", 0)
            score_vol = max(0, 100 - vol * 15)  # 波动率越低分越高

            # 加权总分
            total_score = (
                score_chg * 0.25 +
                score_flow * 0.30 +
                score_cont * 0.20 +
                score_avg5 * 0.15 +
                score_vol * 0.10
            )

            scored.append({
                **b,
                "kline_analysis": cont,
                "scores": {
                    "change": round(score_chg, 1),
                    "flow": round(score_flow, 1),
                    "continuity": round(score_cont, 1),
                    "avg_5d": round(score_avg5, 1),
                    "volatility": round(score_vol, 1),
                    "total": round(total_score, 1),
                },
            })

        # 按总分降序
        scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
        return scored

    def scan(self, top_n: int = 10, board_type: str = "concept") -> List[Dict]:
        """
        完整扫描: 获取全部板块 → 打分 → 返回Top N
        """
        print(f"📡 正在扫描{('概念' if board_type == 'concept' else '行业')}板块...")
        boards = self.fetch_all_boards(board_type)
        print(f"   获取到 {len(boards)} 个板块，开始多因子打分...")
        scored = self.score_boards(boards)
        top = scored[:top_n]
        print(f"✅ 扫描完成，Top {top_n} 板块已选出")
        return top


from typing import Dict
