"""
Telegram Bot — 推送通知
参考: Freqtrade Telegram RPC 模块
"""
import os
from typing import List, Dict


class TelegramNotifier:
    """Telegram 推送通知器"""

    def __init__(self, config: Dict):
        self.enabled = config.get("enabled", False)
        self.token = config.get("bot_token", "")
        self.chat_id = config.get("chat_id", "")
        self.push_level = config.get("push_level", "critical")

    def _send(self, message: str) -> bool:
        """发送消息"""
        if not self.enabled or not self.token or not self.chat_id:
            return False

        try:
            import urllib.request
            import urllib.parse
            import json

            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }).encode()

            req = urllib.request.Request(url, data=data, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result.get("ok", False)
        except Exception as e:
            print(f"[WARN] Telegram发送失败: {e}")
            return False

    def send_advice(self, advice_data: Dict) -> bool:
        """发送14:30研判报告"""
        if not self.enabled:
            return False

        market = advice_data.get("market", {})
        stats = advice_data.get("stats", {})
        positions = advice_data.get("positions", [])
        actions = advice_data.get("action_items", [])

        # 确定推送级别
        critical_count = stats.get("critical_count", 0)
        if self.push_level == "none":
            return False
        if self.push_level == "critical" and critical_count == 0:
            return False

        # 构建消息
        lines = [
            f"<b>📋 下午盘研判 | {advice_data.get('updated', '')[:10]}</b>",
            f"",
            f"🌍 市场: {market.get('label', '?')} | 成交额: {market.get('volume_yi', 0)}亿",
            f"📊 持仓: {stats.get('total_holdings', 0)}只 | 盈亏: {stats.get('total_profit_pct', 0):+.2f}%",
            f"",
        ]

        # 紧急操作
        if critical_count > 0:
            lines.append(f"<b>🔴 紧急操作 ({critical_count})</b>")
            for a in actions:
                if a["urgency"] == "critical":
                    lines.append(f"  {a['message']}")
            lines.append("")

        # 高优先级
        high_count = stats.get("high_count", 0)
        if high_count > 0:
            lines.append(f"<b>🟡 关注 ({high_count})</b>")
            for a in actions:
                if a["urgency"] == "high":
                    lines.append(f"  {a['message']}")
            lines.append("")

        # 费率日历
        fee_cal = advice_data.get("fee_calendar", [])
        if fee_cal:
            lines.append(f"<b>📅 费率解锁</b>")
            for f in fee_cal[:3]:
                lines.append(f"  {f['fund_name'][:10]}: {f['fee_label']} → {f['unlock_date']}")
            lines.append("")

        message = "\n".join(lines)
        return self._send(message)

    def send_simple(self, text: str) -> bool:
        """发送简单文本"""
        return self._send(text)
