"""
Data Fetcher — 统一数据获取层
参考: Qlib 数据层 + Freqtrade 数据管理
数据源: 东方财富(主) / 天天基金(基金) / 新浪(备用)
"""
import json
import time
import urllib.request
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple


class DataFetcher:
    """统一数据获取器"""

    def __init__(self):
        self.headers = {
            "Referer": "https://quote.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.ttjj_headers = {
            "Referer": "https://fund.eastmoney.com/",
            "User-Agent": "Mozilla/5.0"
        }

    def _fetch(self, url: str, headers: Optional[Dict] = None, timeout: int = 15) -> Dict:
        """通用GET请求"""
        h = headers or self.headers
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def fetch_fund_nav(self, fund_code: str, page_size: int = 60) -> List[Dict]:
        """
        获取基金历史净值 (天天基金)
        返回: [{date, nav, acc_nav, daily_change}, ...]
        """
        url = (f"https://api.fund.eastmoney.com/f10/lsjz?"
               f"fundCode={fund_code}&pageIndex=1&pageSize={page_size}")
        try:
            data = self._fetch(url, self.ttjj_headers)
            if data.get("ErrCode") == 0:
                records = data.get("Data", {}).get("LSJZList", [])
                return [
                    {
                        "date": r.get("FSRQ", ""),
                        "nav": float(r.get("DWJZ", 0)),
                        "acc_nav": float(r.get("LJJZ", 0)),
                        "daily_change": float(r.get("JZZZL", 0)) if r.get("JZZZL") else None,
                    }
                    for r in records if r.get("FSRQ")
                ]
        except Exception as e:
            print(f"[WARN] 天天基金{fund_code}获取失败: {e}")
        return []

    def fetch_fund_estimate(self, fund_code: str) -> Optional[Dict]:
        """
        获取基金日内实时估值 (天天基金 fundgz)
        返回: {code, name, nav_estimate, change_pct, update_time}
        """
        try:
            url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js?rt={int(time.time()*1000)}"
            req = urllib.request.Request(url, headers=self.ttjj_headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                text = resp.read().decode()
            start = text.index("{")
            end = text.rindex("}") + 1
            est = json.loads(text[start:end])
            return {
                "code": fund_code,
                "name": est.get("name", ""),
                "nav_estimate": float(est.get("gsz", 0)),
                "change_pct": float(est.get("gszzl", 0)),
                "update_time": est.get("gztime", ""),
            }
        except Exception as e:
            print(f"[WARN] 基金{fund_code}估值获取失败: {e}")
            return None

    def fetch_board_kline(self, board_secid: str, days: int = 60) -> List[Dict]:
        """
        获取板块K线 (东方财富)
        secid格式: 90.BKxxxx
        返回: [{date, open, close, high, low, volume}, ...]
        """
        url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
               f"secid={board_secid}&fields1=f1,f2,f3,f4,f5,f6&"
               f"fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=0&"
               f"end=20500101&lmt={days}")
        try:
            data = self._fetch(url)
            klines = data.get("data", {}).get("klines", [])
            result = []
            for k in klines:
                parts = k.split(",")
                if len(parts) >= 6:
                    result.append({
                        "date": parts[0],
                        "open": float(parts[1]),
                        "close": float(parts[2]),
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": int(parts[5]),
                    })
            return result
        except Exception as e:
            print(f"[WARN] 板块{board_secid}K线获取失败: {e}")
            return []

    def fetch_board_snapshot(self, board_secid: str) -> Optional[Dict]:
        """板块实时快照"""
        url = (f"https://push2.eastmoney.com/api/qt/stock/get?"
               f"secid={board_secid}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f170&"
               f"_={int(time.time()*1000)}")
        try:
            data = self._fetch(url)
            d = data.get("data", {})
            if d:
                return {
                    "price": d.get("f43", 0) / 100 if d.get("f43") else 0,
                    "high": d.get("f44", 0) / 100 if d.get("f44") else 0,
                    "low": d.get("f45", 0) / 100 if d.get("f45") else 0,
                    "open": d.get("f46", 0) / 100 if d.get("f46") else 0,
                    "volume": d.get("f47", 0),
                    "amount": d.get("f48", 0),
                    "change_pct": round(d.get("f170", 0), 2),
                }
        except Exception as e:
            print(f"[WARN] 板块{board_secid}快照获取失败: {e}")
        return None

    def fetch_index_snapshot(self) -> Dict[str, Dict]:
        """五大指数实时快照"""
        indexes = {
            "上证50": "1.000016", "沪深300": "1.000300",
            "中证500": "1.000905", "创业板指": "0.399006", "科创50": "1.000688",
        }
        secids = ",".join(indexes.values())
        url = (f"https://push2.eastmoney.com/api/qt/ulist.np/get?"
               f"fltt=2&fields=f2,f3,f6,f12,f14&secids={secids}&_={int(time.time()*1000)}")
        result = {}
        try:
            data = self._fetch(url)
            if data.get("data", {}).get("diff"):
                for item in data["data"]["diff"]:
                    code = item.get("f12", "")
                    for name, sid in indexes.items():
                        if code == sid.split(".")[-1]:
                            result[name] = {
                                "price": round(item.get("f2", 0), 2),
                                "change_pct": round(item.get("f3", 0), 2),
                                "volume": item.get("f6", 0),
                            }
        except Exception as e:
            print(f"[WARN] 指数快照获取失败: {e}")
        return result

    def fetch_board_ranking(self, top_n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """
        板块涨跌排名
        返回: (top涨幅列表, bottom跌幅列表)
        """
        headers = self.headers.copy()
        try:
            # 涨幅Top
            url_up = (f"https://push2.eastmoney.com/api/qt/clist/get?"
                      f"fid=f3&po=1&pz={top_n}&pn=1&np=1&fltt=2&invt=2&"
                      f"fs=m:90+t:2&fields=f3,f14&_={int(time.time()*1000)}")
            data_up = self._fetch(url_up, headers)
            top = [{"name": d.get("f14", ""), "change_pct": round(d.get("f3", 0), 2)}
                   for d in data_up.get("data", {}).get("diff", [])]

            # 跌幅Top
            url_down = (f"https://push2.eastmoney.com/api/qt/clist/get?"
                        f"fid=f3&po=0&pz={top_n}&pn=1&np=1&fltt=2&invt=2&"
                        f"fs=m:90+t:2&fields=f3,f14&_={int(time.time()*1000)}")
            data_down = self._fetch(url_down, headers)
            bottom = [{"name": d.get("f14", ""), "change_pct": round(d.get("f3", 0), 2)}
                      for d in data_down.get("data", {}).get("diff", [])]
            return top, bottom
        except Exception as e:
            print(f"[WARN] 板块排名获取失败: {e}")
            return [], []

    def fetch_market_volume(self) -> float:
        """两市成交额 (亿元)"""
        url = (f"https://push2.eastmoney.com/api/qt/ulist.np/get?"
               f"fltt=2&fields=f2,f6,f12,f14&secids=1.000001,0.399001&"
               f"_={int(time.time()*1000)}")
        try:
            data = self._fetch(url)
            total = 0
            if data.get("data", {}).get("diff"):
                for item in data["data"]["diff"]:
                    total += (item.get("f6", 0) or 0)
            return round(total / 1e8, 0)
        except Exception as e:
            print(f"[WARN] 成交额获取失败: {e}")
            return 0
