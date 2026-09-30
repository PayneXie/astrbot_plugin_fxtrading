"""FX输出格式化工具。"""
from datetime import datetime
from typing import Any, Dict, List


class Formatters:
    """FX格式化工具类。"""

    @staticmethod
    def format_currency(amount: float, precision: int = 2) -> str:
        """格式化货币金额。"""
        if amount >= 100000000:
            return f"{amount / 100000000:.2f}亿"
        if amount >= 10000:
            return f"{amount / 10000:.2f}万"
        return f"{amount:.{precision}f}"

    @staticmethod
    def format_timestamp(timestamp: int) -> str:
        """格式化时间戳。"""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def format_fx_account_info(account: Dict[str, Any], positions: List[Dict[str, Any]]) -> str:
        """格式化FX账户信息。"""
        lines = [
            "👤 FX账户信息",
            f"💱 结算货币: {account.get('base_currency', 'CNY')}",
            f"💰 账户余额: {Formatters.format_currency(account.get('balance', 0.0))}",
            f"💎 账户净值: {Formatters.format_currency(account.get('equity', 0.0))}",
            f"📈 已实现盈亏: {account.get('realized_pnl', 0.0):+.2f}",
            f"📊 浮动盈亏: {account.get('unrealized_pnl', 0.0):+.2f}",
            f"💸 累计手续费: {account.get('total_fees', 0.0):.2f}",
            f"📦 总敞口: {Formatters.format_currency(account.get('gross_exposure', 0.0))}",
            f"⚙️ 最大杠杆: {account.get('max_leverage', 0.0):.2f}x",
        ]

        if not positions:
            lines.append("\n📊 暂无持仓")
            return "\n".join(lines)

        lines.append("\n📊 当前持仓:")
        for pos in positions:
            side_icon = "🟢 做多" if pos.get("side") == "long" else "🔴 做空"
            lines.append(
                f"{side_icon} {pos.get('symbol_name', pos.get('symbol', 'N/A'))} ({pos.get('symbol', 'N/A')})\n"
                f"   持仓ID: {pos.get('position_id', 'N/A')}\n"
                f"   手数: {pos.get('volume_lots', 0):.2f} 手  杠杆: {pos.get('leverage', 0):.2f}x\n"
                f"   开仓价: {pos.get('open_price', 0):.5f}  现价: {pos.get('current_price', 0):.5f}\n"
                f"   名义价值: {Formatters.format_currency(pos.get('notional_value', 0.0))}\n"
                f"   浮盈亏: {pos.get('unrealized_pnl', 0.0):+.2f}"
            )

        return "\n".join(lines)

    @staticmethod
    def format_fx_ranking(accounts_data: List[Dict[str, Any]], current_user_id: str = None) -> str:
        """格式化FX排行榜。"""
        if not accounts_data:
            return "📊 暂无FX排行数据"

        sorted_accounts = sorted(accounts_data, key=lambda x: x.get("equity", 0), reverse=True)
        lines = ["🏆 群内FX排行榜 (按净值):"]

        for index, account in enumerate(sorted_accounts[:10], 1):
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"{index}."
            name_marker = "👑" if account.get("user_id") == current_user_id else ""
            total_pnl = account.get("realized_pnl", 0.0) + account.get("unrealized_pnl", 0.0)
            pnl_icon = "🟢" if total_pnl >= 0 else "🔴"

            lines.append(
                f"{medal} {account.get('username', '匿名用户')}{name_marker}\n"
                f"   💎 净值: {Formatters.format_currency(account.get('equity', 0.0))}\n"
                f"   {pnl_icon} 总盈亏: {total_pnl:+.2f}\n"
                f"   📦 敞口: {Formatters.format_currency(account.get('gross_exposure', 0.0))}"
            )

        return "\n".join(lines)

    @staticmethod
    def format_fx_order_history(history_data: Dict[str, Any]) -> str:
        """格式化FX历史订单列表。"""
        orders = history_data["orders"]
        current_page = history_data["current_page"]
        total_pages = history_data["total_pages"]
        total_count = history_data["total_count"]

        if not orders:
            return "📋 暂无FX历史订单记录"

        status_map = {
            "filled": "已成交",
            "cancelled": "已撤销",
            "partial": "部分成交",
            "liquidated": "强平成交",
        }

        lines = [f"📋 FX历史订单 (第{current_page}页/共{total_pages}页, 共{total_count}条):"]

        for index, order in enumerate(orders, 1):
            side_text = "🟢做多" if order.get("side") == "long" else "🔴做空"
            intent_text = "开仓" if order.get("intent") == "open" else "平仓"
            status_text = status_map.get(order.get("status"), order.get("status"))

            lines.append(
                f"{index}. {side_text}{intent_text} {order.get('symbol_name', order.get('symbol', 'N/A'))} ({order.get('symbol', 'N/A')})\n"
                f"   ✅ 状态: {status_text}\n"
                f"   💰 价格: {order.get('fill_price', order.get('requested_price', 0)):.5f}  手数: {order.get('volume_lots', 0):.2f} 手\n"
                f"   ⚙️ 杠杆: {order.get('leverage', 0):.2f}x  名义价值: {Formatters.format_currency(order.get('notional_value', 0.0))}\n"
                f"   💸 手续费: {order.get('commission', 0.0):.2f}\n"
                f"   📅 时间: {Formatters.format_timestamp(order.get('update_time', 0))}\n"
                f"   🆔 订单号: {order.get('order_id', 'N/A')}"
            )

        if total_pages > 1:
            page_info = []
            if history_data["has_prev"]:
                page_info.append(f"上一页: /fx历史 {current_page - 1}")
            if history_data["has_next"]:
                page_info.append(f"下一页: /fx历史 {current_page + 1}")
            if page_info:
                lines.append("\n" + " | ".join(page_info))

        return "\n".join(lines)

    @staticmethod
    def format_help_message() -> str:
        """格式化帮助信息。"""
        return """📖 FX 模拟交易使用说明

🚀 快速开始:
/fx注册 - 开通 FX 模拟交易账户

💰 交易指令:
/fx做多 交易对 手数 杠杆
  例: /fx做多 EURUSD 0.10 20
  例: /fx做多 USDJPY 0.20 30

/fx做空 交易对 手数 杠杆
  例: /fx做空 EURUSD 0.10 20

/fx平仓 持仓ID [手数] - 市价平仓
  例: /fx平仓 FXP-12345678
  例: /fx平仓 FXP-12345678 0.05

📊 查询指令:
/fx账户 - 查询 FX 账户与持仓
/fx汇价 [交易对] - 实时汇价
  例: /fx汇价 EURUSD
/fx排行 - 群内 FX 排行
/fx历史 - FX 历史订单
/fx - 查看帮助

⚠️ 交易规则:
• 支持做多、做空、杠杆
• 按交易对中间价模拟报价，并附加点差
• 交易时间按 FX 24/5 执行，并包含日常维护窗口
• 开仓会校验净值与最大杠杆上限
• 开仓和平仓都会收取手续费
• 当账户净值 <= 0 时触发强制平仓
• 仅支持实时成交，不提供限价挂单

💡 提示:
• 支持交易对代码和中文名称搜索
• 周日开盘到周五收盘之间可交易，维护窗口内暂停交易
• 平仓请优先使用账户页展示的持仓ID"""
