"""涨跌停价格获取策略决策器
统一管理何时使用API涨跌停价格，何时使用本地计算
"""
from datetime import datetime
from typing import Tuple, Optional
from enum import Enum
from astrbot.api import logger

from .market_time import market_time_manager


class PriceStrategy(Enum):
    """价格获取策略枚举"""
    API_DIRECT = "api_direct"       # 直接使用API返回的涨跌停价格
    LOCAL_CALCULATE = "local_calc"  # 基于收盘价本地计算涨跌停价格


class PriceStrategyDecider:
    """
    涨跌停价格策略决策器
    
    核心规则：
    - 交易日9:30-15:00（包括午休）：使用API涨跌停价格
    - 其他所有时间：基于API收盘价本地计算涨跌停价格
    """
    
    @staticmethod
    def decide_strategy(current_time: Optional[datetime] = None) -> Tuple[PriceStrategy, str]:
        """
        决定使用哪种价格获取策略
        
        Args:
            current_time: 当前时间，默认为系统当前时间
            
        Returns:
            (策略枚举, 策略说明)
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 检查是否为交易日
        if not market_time_manager.is_trading_day(current_time.date()):
            reason = "非交易日"
            if not market_time_manager.is_weekday(current_time.date()):
                reason = "周末"
            elif market_time_manager.is_holiday(current_time.date()):
                reason = "法定节假日"
            
            logger.debug(f"{reason}，使用本地计算策略")
            return PriceStrategy.LOCAL_CALCULATE, f"{reason}，使用收盘价本地计算涨跌停"
        
        # 交易日：检查是否在9:30-15:00时间段内
        current_time_only = current_time.time()
        market_start = datetime.strptime("09:30", "%H:%M").time()
        market_end = datetime.strptime("15:00", "%H:%M").time()
        
        if market_start <= current_time_only <= market_end:
            # 交易日的9:30-15:00（包括午休时间）：使用API涨跌停
            reason = PriceStrategyDecider._get_market_period_description(current_time_only)
            logger.debug(f"交易日{reason}，使用API策略")
            return PriceStrategy.API_DIRECT, f"交易日{reason}，使用API涨跌停价格"
        else:
            # 交易日的其他时间段：使用本地计算
            if current_time_only < market_start:
                reason = "开盘前"
            else:
                reason = "收盘后"
            
            logger.debug(f"交易日{reason}，使用本地计算策略")
            return PriceStrategy.LOCAL_CALCULATE, f"交易日{reason}，使用收盘价本地计算涨跌停"
    
    @staticmethod
    def _get_market_period_description(current_time) -> str:
        """获取市场时段描述"""
        morning_end = datetime.strptime("11:30", "%H:%M").time()
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        
        if current_time <= morning_end:
            return "上午交易时段"
        elif current_time < afternoon_start:
            return "午休时段"
        else:
            return "下午交易时段"
    
    @staticmethod
    def should_use_api_limit_prices(current_time: Optional[datetime] = None) -> bool:
        """
        便捷方法：判断是否应该使用API涨跌停价格
        
        Args:
            current_time: 当前时间，默认为系统当前时间
            
        Returns:
            是否使用API涨跌停价格
        """
        strategy, _ = PriceStrategyDecider.decide_strategy(current_time)
        return strategy == PriceStrategy.API_DIRECT
    
    @staticmethod
    def should_calculate_locally(current_time: Optional[datetime] = None) -> bool:
        """
        便捷方法：判断是否应该本地计算涨跌停价格
        
        Args:
            current_time: 当前时间，默认为系统当前时间
            
        Returns:
            是否本地计算涨跌停价格
        """
        strategy, _ = PriceStrategyDecider.decide_strategy(current_time)
        return strategy == PriceStrategy.LOCAL_CALCULATE
    
    @staticmethod
    def get_strategy_info(current_time: Optional[datetime] = None) -> dict:
        """
        获取当前策略的详细信息
        
        Args:
            current_time: 当前时间，默认为系统当前时间
            
        Returns:
            策略信息字典
        """
        if current_time is None:
            current_time = datetime.now()
        
        strategy, reason = PriceStrategyDecider.decide_strategy(current_time)
        
        return {
            'strategy': strategy.value,
            'reason': reason,
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'is_trading_day': market_time_manager.is_trading_day(current_time.date()),
            'use_api_limit': strategy == PriceStrategy.API_DIRECT,
            'calculate_local': strategy == PriceStrategy.LOCAL_CALCULATE
        }


# 全局决策器实例
price_strategy_decider = PriceStrategyDecider()
