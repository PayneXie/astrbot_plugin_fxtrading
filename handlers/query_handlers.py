"""查询命令处理器 - 处理所有查询相关命令"""
import asyncio
from typing import AsyncGenerator
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult

from ..services.fx_data import FXDataService
from ..services.trade_coordinator import TradeCoordinator
from ..services.user_interaction import UserInteractionService
from ..utils.formatters import Formatters


class QueryCommandHandlers:
    """查询命令处理器集合"""
    
    def __init__(self, trade_coordinator: TradeCoordinator, user_interaction: UserInteractionService, order_monitor=None, fx_data_service: FXDataService = None):
        self.trade_coordinator = trade_coordinator
        self.user_interaction = user_interaction
        self.order_monitor = order_monitor
        self.fx_data_service = fx_data_service or FXDataService(trade_coordinator.storage)
    
    async def handle_account_info(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """显示FX账户信息。"""
        user_id = self.trade_coordinator.get_isolated_user_id(event)
        
        fx_account_data = self.trade_coordinator.storage.get_fx_account(user_id)
        if not fx_account_data:
            yield MessageEventResult().message("❌ 您还未注册，请先使用 /fx注册 注册账户")
            return
        
        try:
            await self.trade_coordinator.update_user_assets_if_needed(user_id)
            fx_account_data = self.trade_coordinator.storage.get_fx_account(user_id)
            positions = self.trade_coordinator.storage.get_fx_positions(user_id)
            info_text = Formatters.format_fx_account_info(fx_account_data, positions)
            yield MessageEventResult().message(info_text)
        except Exception as e:
            logger.error(f"查询FX账户信息失败: {e}")
            yield MessageEventResult().message("❌ 查询FX账户失败，请稍后重试")
    
    async def handle_stock_price(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """查询汇价（支持模糊搜索）"""
        params = event.message_str.strip().split()[1:]
        
        if not params:
            try:
                quotes = await self.fx_data_service.get_major_quotes(use_cache=False)
                if not quotes:
                    yield MessageEventResult().message("❌ 暂时无法获取主流货币对报价，请稍后重试")
                    return

                lines = ["💱 主流货币对报价"]
                for quote in quotes:
                    lines.append(
                        f"{quote.symbol}  中间价:{quote.mid_price:.5f}  "
                        f"买入:{quote.ask_price:.5f}  卖出:{quote.bid_price:.5f}  "
                        f"涨跌:{quote.change_percent:+.2f}%"
                    )
                lines.append("\n💡 使用 /fx汇价 交易对 查看单个品种详情")
                yield MessageEventResult().message("\n".join(lines))
            except Exception as e:
                logger.error(f"查询主流货币对失败: {e}")
                yield MessageEventResult().message("❌ 查询主流货币对失败，请稍后重试")
            return
        
        keyword = params[0]
        
        try:
            candidates = await self.fx_data_service.search_symbols(keyword)
            if not candidates:
                yield MessageEventResult().message(f"❌ 未找到相关交易对: {keyword}")
                return

            selected_symbol = candidates[0]
            if len(candidates) > 1:
                options = [f"{candidate['name']} ({candidate['symbol']})" for candidate in candidates[:5]]
                prompt_lines = ["🔍 找到多个相关交易对，请选择:\n"]
                for index, candidate in enumerate(candidates[:5], 1):
                    prompt_lines.append(
                        f"{index}. {candidate['name']} ({candidate['symbol']}) "
                        f"[{candidate['base_currency']}/{candidate['quote_currency']}]"
                    )

                selected_index, error_msg = await self.user_interaction.wait_for_choice_selection(
                    event,
                    "\n".join(prompt_lines) + "\n\n💡 请选择要查询的交易对",
                    options,
                )
                if error_msg:
                    yield MessageEventResult().message(error_msg)
                    return
                if selected_index is None:
                    yield MessageEventResult().message("💭 查询已取消")
                    return
                selected_symbol = candidates[selected_index]

            quote = await self.fx_data_service.get_quote(selected_symbol["symbol"], use_cache=False)
            if not quote:
                yield MessageEventResult().message("❌ 无法获取实时汇价")
                return

            info_text = (
                f"💱 {quote.name} ({quote.symbol})\n"
                f"💰 中间价: {quote.mid_price:.5f}\n"
                f"🟢 买入价: {quote.ask_price:.5f}\n"
                f"🔴 卖出价: {quote.bid_price:.5f}\n"
                f"📊 涨跌: {quote.change_amount:+.5f} ({quote.change_percent:+.2f}%)\n"
                f"📈 最高: {quote.high_price:.5f}  📉 最低: {quote.low_price:.5f}\n"
                f"↔️ 点差: {quote.spread():.5f}\n"
                f"⏰ 更新时间: {Formatters.format_timestamp(quote.update_time)}"
            )
            yield MessageEventResult().message(info_text)
                    
        except Exception as e:
            logger.error(f"查询汇价失败: {e}")
            yield MessageEventResult().message("❌ 查询失败，请稍后重试")
    
    async def handle_ranking(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """显示群内FX排行榜。"""
        try:
            platform_name = event.get_platform_name()
            session_id = event.get_session_id()
            session_prefix = f"{platform_name}:"
            session_suffix = f":{session_id}"
            current_user_id = self.trade_coordinator.get_isolated_user_id(event)

            all_fx_accounts = self.trade_coordinator.storage.get_all_fx_accounts()
            fx_accounts_list = [
                account for user_id, account in all_fx_accounts.items()
                if user_id.startswith(session_prefix) and user_id.endswith(session_suffix)
            ]

            if fx_accounts_list:
                update_tasks = [
                    self.trade_coordinator.update_user_assets_if_needed(account["user_id"])
                    for account in fx_accounts_list if account.get("user_id")
                ]
                if update_tasks:
                    await asyncio.gather(*update_tasks, return_exceptions=True)
            
                refreshed_accounts = self.trade_coordinator.storage.get_all_fx_accounts()
                fx_accounts_list = [
                    account for user_id, account in refreshed_accounts.items()
                    if user_id.startswith(session_prefix) and user_id.endswith(session_suffix)
                ]
                ranking_text = Formatters.format_fx_ranking(fx_accounts_list, current_user_id)
                yield MessageEventResult().message(ranking_text)
                return

            if not fx_accounts_list:
                yield MessageEventResult().message("📊 当前群聊暂无用户排行数据\n请先使用 /fx注册 注册账户")
                return
            
        except Exception as e:
            logger.error(f"查询排行榜失败: {e}")
            yield MessageEventResult().message("❌ 查询失败，请稍后重试")
    
    async def handle_order_history(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """显示FX历史订单。"""
        user_id = self.trade_coordinator.get_isolated_user_id(event)
        
        if not self.trade_coordinator.storage.get_fx_account(user_id):
            yield MessageEventResult().message("❌ 您还未注册，请先使用 /fx注册 注册账户")
            return
        
        # 解析页码参数
        params = event.message_str.strip().split()[1:]
        page = 1
        if params:
            try:
                page = int(params[0])
                if page < 1:
                    page = 1
            except ValueError:
                yield MessageEventResult().message("❌ 页码格式错误\n\n格式: /fx历史 [页码]\n例: /fx历史 1")
                return
        
        try:
            history_data = self.trade_coordinator.storage.get_user_fx_order_history(user_id, page)
            history_text = Formatters.format_fx_order_history(history_data)
            yield MessageEventResult().message(history_text)
            
        except Exception as e:
            logger.error(f"查询历史订单失败: {e}")
            yield MessageEventResult().message("❌ 查询失败，请稍后重试")
    
    async def handle_help(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """显示帮助信息"""
        help_text = Formatters.format_help_message()
        yield MessageEventResult().message(help_text)
    
    async def handle_polling_status(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """显示轮询监控状态（管理员专用）"""
        if not self.order_monitor:
            yield MessageEventResult().message("❌ 轮询监控服务未初始化")
            return
        
        try:
            status = self.order_monitor.get_monitor_status()
            market_status = self.fx_data_service.get_market_status()
            
            # 构建状态信息
            status_text = "📊 FX风控监控状态\n\n"
            
            # 运行状态
            if status['is_running']:
                if status['is_paused']:
                    status_text += "⏸️ 状态: 已暂停（间隔为0）\n"
                else:
                    status_text += "✅ 状态: 正在运行\n"
            else:
                status_text += "❌ 状态: 已停止\n"
            
            # 轮询配置
            status_text += f"⏱️ 轮询间隔: {status['current_interval']}秒\n"
            
            # 上次轮询时间
            status_text += f"🕒 上次轮询: {status['last_poll_time']}\n"
            
            # 下次轮询时间
            status_text += f"🕓 下次轮询: {status['next_poll_time']}\n"
            
            # 连通性状态
            connectivity_icon = "🟢" if status['last_connectivity_status'] else "🔴"
            status_text += f"{connectivity_icon} 连通性: {'正常' if status['last_connectivity_status'] else '异常'}\n"
            status_text += f"📈 连通成功率: {status['connectivity_rate']:.1f}% ({status['connectivity_stats']})\n"
            
            # 交易时间状态
            fx_trading_icon = "🟢" if status.get('is_fx_trading_time') else "⭕"
            status_text += f"{fx_trading_icon} FX交易时间: {'是' if status.get('is_fx_trading_time') else '否'}\n"
            status_text += f"🕘 本地时间: {market_status.get('current_time')}\n"
            status_text += f"🌍 UTC时间: {market_status.get('current_utc_time')}\n"
            status_text += f"📍 市场状态: {market_status.get('reason')}\n"
            status_text += f"📆 周度开盘(UTC): 周日 {market_status.get('week_open_utc')}\n"
            status_text += f"📆 周度收盘(UTC): 周五 {market_status.get('week_close_utc')}\n"
            status_text += f"🛠️ 维护窗口(UTC): {market_status.get('daily_break_utc')}\n"
            status_text += "💱 实时成交模式: 已启用"
            
            yield MessageEventResult().message(status_text)
            
        except Exception as e:
            logger.error(f"获取轮询状态失败: {e}")
            yield MessageEventResult().message("❌ 获取轮询状态失败，请稍后重试")
