"""用户管理处理器 - 处理用户注册等相关命令"""
import time
from typing import AsyncGenerator
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult

from ..models.fx_account import FXAccount
from ..services.trade_coordinator import TradeCoordinator
from ..services.user_interaction import UserInteractionService
from ..utils.formatters import Formatters


class UserCommandHandlers:
    """用户命令处理器集合"""
    
    def __init__(self, trade_coordinator: TradeCoordinator, user_interaction: UserInteractionService, storage):
        self.trade_coordinator = trade_coordinator
        self.user_interaction = user_interaction
        self.storage = storage
    
    async def handle_user_registration(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """用户注册"""
        user_id = self.trade_coordinator.get_isolated_user_id(event)
        user_name = event.get_sender_name() or f"用户{user_id}"
        
        # 检查是否已注册
        existing_account = self.trade_coordinator.storage.get_fx_account(user_id)
        if existing_account:
            yield MessageEventResult().message("您已经注册过了！使用 /fx账户 查看账户信息")
            return
        
        try:
            # 创建FX账户，从插件配置获取初始资金与杠杆
            initial_balance = self.storage.get_plugin_config_value('initial_balance', 1000000)
            default_leverage = self.storage.get_plugin_config_value('fx_default_max_leverage', 20.0)
            account = FXAccount(
                user_id=user_id,
                username=user_name,
                base_currency="CNY",
                balance=initial_balance,
                equity=initial_balance,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                gross_exposure=0.0,
                max_leverage=default_leverage,
                liquidation_enabled=True,
                register_time=int(time.time()),
                last_login=int(time.time()),
                total_fees=0.0,
            )
            
            # 保存FX账户
            self.trade_coordinator.storage.save_fx_account(user_id, account.to_dict())
            
            yield MessageEventResult().message(
                "🎉 FX模拟账户注册成功！\n"
                f"👤 用户名: {user_name}\n"
                f"💰 初始资金: {Formatters.format_currency(initial_balance)}\n"
                f"⚙️ 最大杠杆: {default_leverage:.2f}x\n"
                "💥 强平规则: 账户净值 <= 0 时强制平仓\n\n"
                "📖 输入 /fx账户 查看账户信息"
            )
            
        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            yield MessageEventResult().message("❌ 注册失败，请稍后重试")
