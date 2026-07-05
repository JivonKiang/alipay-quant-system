"""
Pre-cache Script — 周末预缓存
提前下载全量基金列表 + 识别C类 + 拉取历史净值 + 计算胜率
周一只需轻量扫描板块即可出推荐

用法: python tools/precache.py
输出: output/precached_funds.json (所有C类基金的胜率数据)
"""
import json
import os
import sys
import time
import math
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.fund_screener import FundScreener


# 只需历史净值的API (api.fund.eastmoney.com) 周末通常可用
# 基金列表 (fundcode_search.js) 周末也可用


def precache():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    cache_path = os.path.join(output_dir, "precached_funds.json")

    screener = FundScreener()
    start_time = datetime.now()

    # ===== Step 1: 下载全量基金列表 =====
    print(f"\n{'='*60}")
    print(f"🔄 周末预缓存启动 — {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    print(f"\n📌 Step 1/3: 下载全量基金列表...")
    fund_list = screener.fetch_fund_list()
    print(f"   全量基金: {len(fund_list)} 只")

    # ===== Step 2: 识别全部C类基金 =====
    print(f"\n📌 Step 2/3: 识别C类基金...")
    c_funds = []
    exclude_count = 0
    for f in fund_list:
        name = f.get("name", "")
        code = f.get("code", "")
        if screener.is_c_class_fund(name):
            if screener.is_excluded(name):
                exclude_count += 1
                continue
            c_funds.append(f)
    print(f"   C类基金: {len(c_funds)} 只 (排除 {exclude_count} 只货币/理财)")

    # ===== Step 3: 拉取历史净值 + 计算胜率 =====
    print(f"\n📌 Step 3/3: 拉取历史净值 + 计算胜率 (每个基金间隔0.5s)...")
    print(f"   预计耗时: {len(c_funds) * 0.5 / 60:.0f} 分钟")

    # 按板块关键词分组
    all_keywords = set()
    for kw_list in screener.board_keywords.values():
        all_keywords.update(kw_list)

    # 为每只C类基金分配匹配的板块关键词
    fund_keyword_map = {}
    for f in c_funds:
        matched = []
        name = f["name"]
        for board_name, keywords in screener.board_keywords.items():
            for kw in keywords:
                if kw in name:
                    matched.append(board_name)
                    break
        fund_keyword_map[f["code"]] = list(set(matched))

    # 计算无板块关键词匹配的数量
    no_match = sum(1 for v in fund_keyword_map.values() if not v)
    print(f"   有板块匹配: {len(c_funds) - no_match} 只")
    print(f"   无板块匹配: {no_match} 只 (仍缓存，备用)")

    # 拉取净值 + 计算胜率
    results = {}
    failed = 0
    skipped = 0

    for i, f in enumerate(c_funds):
        code = f["code"]
        name = f["name"]

        # 优先拉取有板块匹配的基金 (它们更可能被推荐)
        if not fund_keyword_map.get(code) and i > 200:
            skipped += 1
            continue  # 跳过无匹配的冷门基金 (限制总拉取量)

        try:
            nav_data = screener.fetch_fund_nav_history(code, 365)
            if len(nav_data) < 30:
                failed += 1
                continue

            analysis = screener.analyze_fund_history(nav_data)
            if "error" in analysis:
                failed += 1

            results[code] = {
                "code": code,
                "name": name,
                "type": f.get("type", ""),
                "matched_boards": fund_keyword_map.get(code, []),
                "analysis": analysis,
            }

            # 进度输出
            if (i + 1) % 20 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                eta = (len(c_funds) - i - 1) * 0.5 / 60
                print(f"   进度: {i+1}/{len(c_funds)} | "
                      f"成功 {len(results)} | 失败 {failed} | "
                      f"跳过 {skipped} | "
                      f"已用 {elapsed:.0f}s | 预计剩余 {eta:.0f}min")

        except Exception as e:
            failed += 1

        time.sleep(0.5)

    # ===== 保存缓存 =====
    cache_data = {
        "cache_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cache_type": "weekend_precache",
        "total_c_funds": len(c_funds),
        "cached_funds": len(results),
        "failed_funds": failed,
        "skipped_funds": skipped,
        "fund_keywords_map": {
            code: boards for code, boards in fund_keyword_map.items() if boards
        },
        "all_keywords": list(all_keywords),
        "funds": results,
    }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ 预缓存完成!")
    print(f"   耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"   缓存文件: {cache_path}")
    print(f"   C类基金总数: {len(c_funds)}")
    print(f"   已缓存净值+胜率: {len(results)} 只")
    print(f"   失败: {failed} 只")
    print(f"   跳过: {skipped} 只")
    print(f"\n   周一推荐时只需:")
    print(f"   1. 扫描热门板块排名 (API)")
    print(f"   2. 从缓存中按板块关键词取出基金")
    print(f"   3. 直接使用缓存的胜率数据 (无需再拉净值)")
    print(f"   4. 生成推荐报告")
    print(f"{'='*60}")


if __name__ == "__main__":
    precache()
