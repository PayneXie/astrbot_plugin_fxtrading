"""FX模拟交易插件。"""
import asyncio
from datetime import datetime, time as dt_time, timedelta
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig
from astrbot.core.star.filter.permission import PermissionType

# 导入重构后的处理器
from .handlers.trading_handlers import TradingCommandHandlers
from .handlers.query_handlers import QueryCommandHandlers
from .handlers.user_handlers import UserCommandHandlers

# 导入服务层
from .services.trade_coordinator import TradeCoordinator
from .services.user_interaction import UserInteractionService
from .services.fx_data import FXDataService
from .services.fx_trading_engine import FXTradingEngine
from .services.order_monitor import OrderMonitorService
from .utils.data_storage import DataStorage


class PaperTradingPlugin(Star):
    """
    FX模拟交易插件
    
    功能特点：
    - 🎯 实时 FX 模拟交易体验：做多、做空、平仓
    - 📊 实时汇价查询和持仓管理
    - 🏆 群内 FX 排行榜
    - ⚡ 基于 AkShare 数据的实时成交
    - 🛡️ 杠杆和强平机制
    - 🤝 真正的用户交互等待机制
    """
    
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context, config)
        self.plugin_config = config  # 保存插件配置
        self.astrbot_config: AstrBotConfig = context.get_config()  # AstrBot全局配置
        self._maintenance_task = None
        
        # 初始化服务层（依赖注入模式）
        self._initialize_services()
        
        # 初始化命令处理器
        self._initialize_handlers()
        
        logger.info("FX模拟交易插件初始化完成")
    
    def _initialize_services(self):
        """初始化服务层"""
        # 数据存储服务 - 传递插件配置
        self.storage = DataStorage("fxtrading", self.plugin_config)
        
        self.fx_data_service = FXDataService(self.storage)
        
        self.fx_trading_engine = FXTradingEngine(self.storage, self.fx_data_service)
        
        # 交易协调器服务
        self.trade_coordinator = TradeCoordinator(self.storage, self.fx_data_service)
        
        # 用户交互服务
        self.user_interaction = UserInteractionService()
        
        # 风控监控服务
        self.order_monitor = OrderMonitorService(self.storage)
    
    def _initialize_handlers(self):
        """初始化命令处理器"""
        # 交易命令处理器
        self.trading_handlers = TradingCommandHandlers(
            self.trade_coordinator, 
            self.user_interaction,
            self.fx_data_service,
            self.fx_trading_engine,
        )
        
        # 查询命令处理器
        self.query_handlers = QueryCommandHandlers(
            self.trade_coordinator, 
            self.user_interaction,
            self.order_monitor,
            self.fx_data_service,
        )
        
        # 用户管理处理器
        self.user_handlers = UserCommandHandlers(
            self.trade_coordinator, 
            self.user_interaction, 
            self.storage  # 传递storage而不是config
        )
    
    async def initialize(self):
        """插件初始化（AstrBot生命周期方法）"""
        try:
            # 启动风控监控服务
            monitor_interval = self.storage.get_plugin_config_value("monitor_interval", 15)
            if monitor_interval > 0:
                await self.order_monitor.start_monitoring()
                logger.info(f"风控监控服务已启动，轮询间隔: {monitor_interval}秒")
            else:
                logger.info("轮询间隔为0，风控监控服务暂停")
            
            # 注册定时任务
            if not self._maintenance_task or self._maintenance_task.done():
                self._maintenance_task = asyncio.create_task(self._daily_maintenance_task())
            
            logger.info("FX模拟交易插件启动完成")
        except Exception as e:
            logger.error(f"插件初始化失败: {e}")
    
    async def terminate(self):
        """插件销毁（AstrBot生命周期方法）"""
        try:
            # 停止风控监控
            await self.order_monitor.stop_monitoring()
            if self._maintenance_task:
                self._maintenance_task.cancel()
                try:
                    await self._maintenance_task
                except asyncio.CancelledError:
                    pass
                self._maintenance_task = None
            logger.info("FX模拟交易插件已停止")
        except Exception as e:
            logger.error(f"插件停止时出错: {e}")
    
    async def _daily_maintenance_task(self):
        """每日维护任务"""        
        while True:
            try:
                # 每天凌晨2点执行维护
                now = datetime.now()
                target_time = datetime.combine(now.date(), dt_time(2, 0))
                
                if now > target_time:
                    # 修复日期计算错误：使用timedelta避免跨月问题
                    target_time = target_time + timedelta(days=1)
                
                sleep_seconds = (target_time - now).total_seconds()
                await asyncio.sleep(sleep_seconds)
                
                # 执行维护任务
                await self._perform_daily_maintenance()
                
            except Exception as e:
                logger.error(f"每日维护任务错误: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时
    
    async def _perform_daily_maintenance(self):
        """执行每日维护"""
        logger.info("开始执行每日维护任务")
        
        try:
            # 刷新所有FX账户并更新强平状态
            all_accounts = self.storage.get_all_fx_accounts()
            for user_id in all_accounts:
                try:
                    await self.fx_trading_engine.update_account_state(user_id)
                except Exception as e:
                    logger.error(f"更新FX账户 {user_id} 数据失败: {e}")
            
            # 清理过期的市场数据缓存
            self.storage.clear_market_cache()
            
            logger.info("每日维护任务完成")
        except Exception as e:
            logger.error(f"每日维护任务执行失败: {e}")

    # ==================== 用户管理命令 ====================
    
    @filter.command("fx注册")
    async def register_user(self, event: AstrMessageEvent):
        """用户注册"""
        async for result in self.user_handlers.handle_user_registration(event):
            yield result

    # ==================== 交易命令 ====================
    
    @filter.command("fx做多")
    async def long_fx(self, event: AstrMessageEvent):
        """做多开仓"""
        async for result in self.trading_handlers.handle_long_open(event):
            yield result
    
    @filter.command("fx做空")
    async def short_fx(self, event: AstrMessageEvent):
        """做空开仓"""
        async for result in self.trading_handlers.handle_short_open(event):
            yield result
    
    @filter.command("fx平仓")
    async def close_position(self, event: AstrMessageEvent):
        """平仓"""
        async for result in self.trading_handlers.handle_close_position(event):
            yield result

    # ==================== 查询命令 ====================
    
    @filter.command("fx账户")
    async def show_account_info(self, event: AstrMessageEvent):
        """显示账户信息"""
        async for result in self.query_handlers.handle_account_info(event):
            yield result
    
    @filter.command("fx汇价")
    async def show_fx_quote(self, event: AstrMessageEvent):
        """查询汇价"""
        async for result in self.query_handlers.handle_fx_quote(event):
            yield result

    @filter.command("fx排行")
    async def show_ranking(self, event: AstrMessageEvent):
        """显示群内排行榜"""
        async for result in self.query_handlers.handle_ranking(event):
            yield result
    
    @filter.command("fx历史")
    async def show_order_history(self, event: AstrMessageEvent):
        """显示历史订单"""
        async for result in self.query_handlers.handle_order_history(event):
            yield result
    
    @filter.command("fx")
    async def show_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        async for result in self.query_handlers.handle_help(event):
            yield result
    
    # ==================== 管理员命令 ====================
    
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("fx状态")
    async def show_polling_status(self, event: AstrMessageEvent):
        """显示轮询监控状态（管理员专用）"""
        async for result in self.query_handlers.handle_polling_status(event):
            yield result
