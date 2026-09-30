"""格式化工具"""
from typing import List, Dict, Any
from datetime import datetime
import time


class Formatters:
    """格式化工具类"""
    
    @staticmethod
    def format_currency(amount: float, precision: int = 2) -> str:
        """格式化货币金额"""
        if amount >= 100000000:  # 1亿
            return f"{amount/100000000:.2f}亿"
        elif amount >= 10000:     # 1万
            return f"{amount/10000:.2f}万"
        else:
            return f"{amount:.{precision}f}"
    
    @staticmethod
    def format_percentage(value: float, precision: int = 2) -> str:
        """格式化百分比"""
        return f"{value:.{precision}f}%"
    
    @staticmethod
    def format_timestamp(timestamp: int) -> str:
        """格式化时间戳"""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def format_stock_info(stock_info: Dict[str, Any]) -> str:
        """格式化股票信息"""
        lines = [
            f"📈 {stock_info['name']} ({stock_info['code']})",
            f"💰 当前价: {stock_info['current_price']:.2f}元",
            f"📊 涨跌: {stock_info['change_amount']:+.2f} ({stock_info['change_percent']:+.2f}%)",
            f"📈 最高: {stock_info['high_price']:.2f} 📉 最低: {stock_info['low_price']:.2f}",
            f"💰 成交额: {Formatters.format_currency(stock_info['turnover'])}元"
        ]
        
        if stock_info.get('is_suspended'):
            lines.append("⏸️ 状态: 停牌")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_user_info(user: Dict[str, Any], positions: List[Dict[str, Any]], frozen_funds: float = 0.0) -> str:
        """格式化用户信息（合并持仓、余额、订单查询）"""
        lines = [
            f"👤 账户信息",
            f"💰 可用余额: {Formatters.format_currency(user['balance'])}元",
            f"💎 总资产: {Formatters.format_currency(user['total_assets'])}元"
        ]
        
        # 如果有冻结资金，显示冻结资金信息
        if frozen_funds > 0:
            lines.append(f"🔒 冻结资金: {Formatters.format_currency(frozen_funds)}元 (买入挂单)")
            lines.append(f"💳 实际可用: {Formatters.format_currency(user['balance'])}元")
        
        if positions:
            lines.append("\n📊 持仓详情:")
            total_market_value = 0
            total_profit_loss = 0
            
            for pos in positions:
                if pos['total_volume'] > 0:
                    profit_color = "🟢" if pos['profit_loss'] >= 0 else "🔴"
                    lines.append(
                        f"{profit_color} {pos['stock_name']}({pos['stock_code']})\n"
                        f"   数量: {pos['total_volume']}股 (可卖: {pos['available_volume']}股)\n"
                        f"   成本: {pos['avg_cost']:.2f}元 现价: {pos['last_price']:.2f}元\n"
                        f"   市值: {Formatters.format_currency(pos['market_value'])}元\n"
                        f"   盈亏: {pos['profit_loss']:+.2f}元 ({pos['profit_loss_percent']:+.2f}%)"
                    )
                    total_market_value += pos['market_value']
                    total_profit_loss += pos['profit_loss']
            
            lines.append(f"\n💼 持仓市值: {Formatters.format_currency(total_market_value)}元")
            profit_color = "🟢" if total_profit_loss >= 0 else "🔴"
            lines.append(f"{profit_color} 总盈亏: {total_profit_loss:+.2f}元")
        else:
            lines.append("\n📊 暂无持仓")
        
        return "\n".join(lines)

    @staticmethod
    def format_fx_account_info(account: Dict[str, Any], positions: List[Dict[str, Any]]) -> str:
        """格式化FX账户信息"""
        lines = [
            "👤 FX账户信息",
            f"💱 结算货币: {account.get('base_currency', 'CNY')}",
            f"💰 账户余额: {Formatters.format_currency(account.get('balance', 0.0))}",
            f"💎 账户净值: {Formatters.format_currency(account.get('equity', 0.0))}",
            f"📈 已实现盈亏: {account.get('realized_pnl', 0.0):+.2f}",
            f"📊 浮动盈亏: {account.get('unrealized_pnl', 0.0):+.2f}",
            f"📦 总敞口: {Formatters.format_currency(account.get('gross_exposure', 0.0))}",
            f"⚙️ 最大杠杆: {account.get('max_leverage', 0.0):.2f}x",
        ]

        if positions:
            lines.append("\n📊 当前持仓:")
            for pos in positions:
                side_icon = "🟢 做多" if pos.get('side') == 'long' else "🔴 做空"
                lines.append(
                    f"{side_icon} {pos.get('symbol_name', pos.get('symbol', 'N/A'))} ({pos.get('symbol', 'N/A')})\n"
                    f"   持仓ID: {pos.get('position_id', 'N/A')}\n"
                    f"   手数: {pos.get('volume_lots', 0):.2f} 手  杠杆: {pos.get('leverage', 0):.2f}x\n"
                    f"   开仓价: {pos.get('open_price', 0):.5f}  现价: {pos.get('current_price', 0):.5f}\n"
                    f"   名义价值: {Formatters.format_currency(pos.get('notional_value', 0.0))}\n"
                    f"   浮盈亏: {pos.get('unrealized_pnl', 0.0):+.2f}"
                )
        else:
            lines.append("\n📊 暂无持仓")

        return "\n".join(lines)
    
    @staticmethod
    def format_order_info(order: Dict[str, Any]) -> str:
        """格式化订单信息"""
        order_type_icon = "🟢" if order['order_type'] == 'buy' else "🔴"
        status_icons = {
            'pending': '⏳',
            'filled': '✅',
            'cancelled': '❌',
            'partial': '🔄'
        }
        status_icon = status_icons.get(order['status'], '❓')
        
        lines = [
            f"{order_type_icon} {order['stock_name']}({order['stock_code']})",
            f"{status_icon} 状态: {order['status']}",
            f"💰 价格: {order['order_price']:.2f}元",
            f"📊 数量: {order['order_volume']}股"
        ]
        
        if order['filled_volume'] > 0:
            lines.append(f"✅ 已成交: {order['filled_volume']}股")
        
        lines.append(f"⏰ 时间: {Formatters.format_timestamp(order['create_time'])}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_pending_orders(orders: List[Dict[str, Any]]) -> str:
        """格式化待成交订单列表"""
        if not orders:
            return "📋 暂无待成交订单"
        
        lines = ["📋 待成交订单:"]
        for i, order in enumerate(orders, 1):
            order_type_icon = "🟢买入" if order['order_type'] == 'buy' else "🔴卖出"
            lines.append(
                f"{i}. {order_type_icon} {order['stock_name']}({order['stock_code']})\n"
                f"   价格: {order['order_price']:.2f}元 数量: {order['order_volume']}股\n"
                f"   订单号: {order['order_id']}"
            )
        
        return "\n".join(lines)
    
    @staticmethod
    def format_ranking(users_data: List[Dict[str, Any]], current_user_id: str = None) -> str:
        """格式化排行榜"""
        if not users_data:
            return "📊 暂无排行数据"
        
        # 按总资产排序
        sorted_users = sorted(users_data, key=lambda x: x.get('total_assets', 0), reverse=True)
        
        lines = ["🏆 群内排行榜 (按总资产):"]
        
        for i, user in enumerate(sorted_users[:10], 1):  # 显示前10名
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            profit_loss = user.get('total_assets', 0) - 1000000  # 减去初始资金
            profit_color = "🟢" if profit_loss >= 0 else "🔴"
            
            # 标记当前用户
            name_marker = "👑" if user.get('user_id') == current_user_id else ""
            
            lines.append(
                f"{medal} {user.get('username', '匿名用户')}{name_marker}\n"
                f"   💎 总资产: {Formatters.format_currency(user.get('total_assets', 0))}元\n"
                f"   {profit_color} 盈亏: {profit_loss:+.2f}元"
            )
        
        return "\n".join(lines)

    @staticmethod
    def format_fx_ranking(accounts_data: List[Dict[str, Any]], current_user_id: str = None) -> str:
        """格式化FX排行榜"""
        if not accounts_data:
            return "📊 暂无FX排行数据"

        sorted_accounts = sorted(accounts_data, key=lambda x: x.get('equity', 0), reverse=True)
        lines = ["🏆 群内FX排行榜 (按净值):"]

        for index, account in enumerate(sorted_accounts[:10], 1):
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"{index}."
            name_marker = "👑" if account.get('user_id') == current_user_id else ""
            total_pnl = account.get('realized_pnl', 0.0) + account.get('unrealized_pnl', 0.0)
            pnl_icon = "🟢" if total_pnl >= 0 else "🔴"

            lines.append(
                f"{medal} {account.get('username', '匿名用户')}{name_marker}\n"
                f"   💎 净值: {Formatters.format_currency(account.get('equity', 0.0))}\n"
                f"   {pnl_icon} 总盈亏: {total_pnl:+.2f}\n"
                f"   📦 敞口: {Formatters.format_currency(account.get('gross_exposure', 0.0))}"
            )

        return "\n".join(lines)
    
    @staticmethod
    def format_order_history(history_data: Dict[str, Any]) -> str:
        """格式化历史订单列表"""
        orders = history_data['orders']
        current_page = history_data['current_page']
        total_pages = history_data['total_pages']
        total_count = history_data['total_count']
        
        if not orders:
            return "📋 暂无历史订单记录"
        
        # 状态中文映射
        status_map = {
            'filled': '已成交',
            'cancelled': '已撤销', 
            'partial': '部分成交'
        }
        
        lines = [f"📋 历史订单 (第{current_page}页/共{total_pages}页, 共{total_count}条):"]
        
        for i, order in enumerate(orders, 1):
            order_type_icon = "🟢买入" if order['order_type'] == 'buy' else "🔴卖出"
            status_text = status_map.get(order['status'], order['status'])
            
            # 根据状态选择图标
            status_icon = "✅" if order['status'] == 'filled' else "❌" if order['status'] == 'cancelled' else "🔄"
            
            lines.append(
                f"{i}. {order_type_icon} {order['stock_name']}({order['stock_code']})\n"
                f"   {status_icon} 状态: {status_text}\n"
                f"   💰 价格: {order['order_price']:.2f}元 数量: {order['order_volume']}股\n"
                f"   📅 时间: {Formatters.format_timestamp(order['update_time'])}\n"
                f"   🆔 订单号: {order['order_id']}"
            )
        
        # 添加分页提示
        if total_pages > 1:
            page_info = []
            if history_data['has_prev']:
                page_info.append(f"上一页: /fx历史 {current_page - 1}")
            if history_data['has_next']:
                page_info.append(f"下一页: /fx历史 {current_page + 1}")
            
            if page_info:
                lines.append("\n" + " | ".join(page_info))
        
        return "\n".join(lines)

    @staticmethod
    def format_fx_order_history(history_data: Dict[str, Any]) -> str:
        """格式化FX历史订单列表"""
        orders = history_data['orders']
        current_page = history_data['current_page']
        total_pages = history_data['total_pages']
        total_count = history_data['total_count']

        if not orders:
            return "📋 暂无FX历史订单记录"

        status_map = {
            'filled': '已成交',
            'cancelled': '已撤销',
            'partial': '部分成交',
            'liquidated': '强平成交'
        }

        lines = [f"📋 FX历史订单 (第{current_page}页/共{total_pages}页, 共{total_count}条):"]

        for index, order in enumerate(orders, 1):
            side_text = "🟢做多" if order.get('side') == 'long' else "🔴做空"
            intent_text = "开仓" if order.get('intent') == 'open' else "平仓"
            status_text = status_map.get(order.get('status'), order.get('status'))

            lines.append(
                f"{index}. {side_text}{intent_text} {order.get('symbol_name', order.get('symbol', 'N/A'))} ({order.get('symbol', 'N/A')})\n"
                f"   ✅ 状态: {status_text}\n"
                f"   💰 价格: {order.get('fill_price', order.get('requested_price', 0)):.5f}  手数: {order.get('volume_lots', 0):.2f} 手\n"
                f"   ⚙️ 杠杆: {order.get('leverage', 0):.2f}x  名义价值: {Formatters.format_currency(order.get('notional_value', 0.0))}\n"
                f"   📅 时间: {Formatters.format_timestamp(order.get('update_time', 0))}\n"
                f"   🆔 订单号: {order.get('order_id', 'N/A')}"
            )

        if total_pages > 1:
            page_info = []
            if history_data['has_prev']:
                page_info.append(f"上一页: /fx历史 {current_page - 1}")
            if history_data['has_next']:
                page_info.append(f"下一页: /fx历史 {current_page + 1}")
            if page_info:
                lines.append("\n" + " | ".join(page_info))

        return "\n".join(lines)
    
    @staticmethod
    def format_help_message() -> str:
        """格式化帮助信息"""
        return """📖 FX 模拟交易使用说明

🚀 快速开始:
/fx注册 - 开通 FX 模拟交易账户

💰 交易指令:
/fx买入 交易对 手数 杠杆 - 市价做多开仓
  例: /fx买入 EURUSD 0.10 20
  例: /fx买入 USDJPY 0.20 30

/fx卖出 交易对 手数 杠杆 - 市价做空开仓
  例: /fx卖出 EURUSD 0.10 20

/fx平仓 持仓ID [手数] - 市价平仓
  例: /fx平仓 FXP-12345678
  例: /fx平仓 FXP-12345678 0.05

📊 查询指令:
/fx账户 - 查询 FX 账户与持仓
/fx汇价 交易对 - 实时汇价
  例: /fx汇价 EURUSD
/fx排行 - 群内 FX 排行
/fx历史 - FX 历史订单
/fx - 查看帮助

⚠️ 交易规则:
• 支持做多、做空、杠杆
• 按交易对中间价模拟报价，并附加点差
• 开仓会校验净值与最大杠杆上限
• 当账户净值 <= 0 时触发强制平仓
• 仅支持实时成交，不提供限价挂单

💡 提示:
• 支持交易对代码和中文名称搜索
• 工作日默认可交易，周末休市
• 平仓请优先使用账户页展示的持仓ID"""
