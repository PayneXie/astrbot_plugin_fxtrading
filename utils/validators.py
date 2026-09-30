"""数据验证工具"""
import re
from typing import Optional


class Validators:
    """数据验证器"""
    
    @staticmethod
    def is_valid_stock_code(code: str) -> bool:
        """验证股票代码格式"""
        if not code or not isinstance(code, str):
            return False
        
        # 去除前后空格并转换为大写
        code = code.strip().upper()
        
        # A股股票代码格式: 6位数字
        # 上海A股: 60xxxx, 68xxxx
        # 深圳A股: 00xxxx, 30xxxx (创业板)
        # 北交所: 43xxxx, 83xxxx, 87xxxx
        pattern = r'^(00|30|60|68|43|83|87)\d{4}$'
        if not re.match(pattern, code):
            return False
        
        # 排除指数代码（不允许交易指数）
        # A股指数代码规律：
        # - 深市指数：399xxx格式
        # - 000xxx开头的都是深市普通股票，不应排除
        index_codes = {
            '399001',  # 深证成指
            '399005',  # 中小100/中小板
            '399006',  # 创业板指
            # 注意：000016是深市股票，000300是深市股票，000688是国城矿业
            # 这些都不应该被排除！指数通过不同的secid格式访问
        }
        
        return code not in index_codes
    
    @staticmethod
    def normalize_stock_code(code: str) -> Optional[str]:
        """标准化股票代码"""
        if not Validators.is_valid_stock_code(code):
            return None
        return code.strip().upper()
    
    @staticmethod
    def is_valid_price(price: float) -> bool:
        """验证价格是否有效"""
        return price > 0 and price < 10000  # 假设股价不会超过10000元
    
    @staticmethod
    def is_valid_volume(volume: int) -> bool:
        """验证交易数量是否有效"""
        # A股最小交易单位是100股（1手）
        return volume > 0 and volume % 100 == 0
    
    @staticmethod
    def is_valid_amount(amount: float) -> bool:
        """验证交易金额是否有效"""
        return amount > 0 and amount < 100000000  # 不超过1亿
    
    @staticmethod
    def is_valid_user_id(user_id: str) -> bool:
        """验证用户ID格式"""
        return bool(user_id and isinstance(user_id, str) and len(user_id.strip()) > 0)
    
    @staticmethod
    def format_stock_code_with_exchange(code: str) -> Optional[str]:
        """为股票代码添加交易所前缀（akshare需要）"""
        code = Validators.normalize_stock_code(code)
        if not code:
            return None
        
        # 根据代码判断交易所
        if code.startswith(('60', '68')):
            return f'sh{code}'  # 上海证券交易所
        elif code.startswith(('00', '30')):
            return f'sz{code}'  # 深圳证券交易所
        elif code.startswith(('43', '83', '87')):
            return f'bj{code}'  # 北京证券交易所
        else:
            return None
    
    @staticmethod
    def parse_order_params(params: list) -> dict:
        """解析订单参数"""
        result = {
            'stock_code': None,
            'volume': None,
            'price': None,
            'is_market_order': True,
            'error': None
        }
        
        if len(params) < 2:
            result['error'] = "参数不足，至少需要股票代码和数量"
            return result
        
        # 解析股票代码
        stock_code = Validators.normalize_stock_code(params[0])
        if not stock_code:
            result['error'] = f"无效的股票代码: {params[0]}"
            return result
        result['stock_code'] = stock_code
        
        # 解析数量
        try:
            volume = int(params[1])
            if not Validators.is_valid_volume(volume):
                result['error'] = f"无效的交易数量: {volume}，必须是100的倍数"
                return result
            result['volume'] = volume
        except ValueError:
            result['error'] = f"无效的数量格式: {params[1]}"
            return result
        
        # 解析价格（可选）
        if len(params) >= 3:
            try:
                price = float(params[2])
                if not Validators.is_valid_price(price):
                    result['error'] = f"无效的价格: {price}"
                    return result
                result['price'] = price
                result['is_market_order'] = False
            except ValueError:
                result['error'] = f"无效的价格格式: {params[2]}"
                return result
        
        return result
    
    @staticmethod
    def validate_order_amount(volume: int, price: float, min_amount: float = 100) -> bool:
        """验证订单金额是否满足最小要求"""
        total_amount = volume * price
        return total_amount >= min_amount
