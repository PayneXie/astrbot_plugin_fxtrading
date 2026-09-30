"""FX market data service powered by AkShare."""
import asyncio
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from astrbot.api import logger

from ..models.fx_quote import FXQuote
from ..utils.data_storage import DataStorage

try:
    import akshare as ak
except ImportError:
    ak = None


class FXDataService:
    """Fetch and search FX quotes from AkShare."""

    CACHE_PREFIX = "fx:"

    def __init__(self, storage: DataStorage):
        self.storage = storage
        self._cache_ttl = int(self.storage.get_plugin_config_value("fx_quote_cache_seconds", 15))
        self._spread_ratio = float(self.storage.get_plugin_config_value("fx_spread_ratio", 0.0002))

    def _normalize_symbol(self, symbol: str) -> str:
        if not symbol:
            return ""
        normalized = "".join(ch for ch in symbol.upper().strip() if ch.isalnum())
        if len(normalized) < 6:
            return normalized
        return normalized[:6] if normalized[:6].isalpha() else normalized

    def _cache_key(self, symbol: str) -> str:
        return f"{self.CACHE_PREFIX}{self._normalize_symbol(symbol)}"

    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        update_time = int(cache_data.get("update_time", 0) or 0)
        return update_time > 0 and (int(time.time()) - update_time) <= self._cache_ttl

    async def _fetch_spot_table(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch full FX spot table from AkShare in a worker thread."""
        if ak is None:
            logger.error("AkShare 未安装，无法获取FX实时行情")
            return None

        try:
            dataframe = await asyncio.to_thread(ak.forex_spot_em)
            if dataframe is None or dataframe.empty:
                return None
            records = dataframe.to_dict("records")
            return records
        except Exception as exc:
            logger.error(f"获取FX实时行情失败: {exc}")
            return None

    async def _fetch_hist_table(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch FX history from AkShare in a worker thread."""
        if ak is None:
            logger.error("AkShare 未安装，无法获取FX历史行情")
            return None

        normalized_symbol = self._normalize_symbol(symbol)
        try:
            dataframe = await asyncio.to_thread(ak.forex_hist_em, symbol=normalized_symbol)
            if dataframe is None or dataframe.empty:
                return None
            return dataframe.to_dict("records")
        except Exception as exc:
            logger.error(f"获取FX历史行情失败 {normalized_symbol}: {exc}")
            return None

    def _row_to_quote(self, row: Dict[str, Any]) -> Optional[FXQuote]:
        symbol = self._normalize_symbol(str(row.get("代码", "")))
        if len(symbol) < 6:
            return None

        try:
            return FXQuote.from_akshare_spot(row, spread_ratio=self._spread_ratio)
        except Exception as exc:
            logger.warning(f"构建FXQuote失败 {symbol}: {exc}")
            return None

    async def get_quote(self, symbol: str, use_cache: bool = True) -> Optional[FXQuote]:
        """Get a single FX quote by symbol."""
        normalized_symbol = self._normalize_symbol(symbol)
        if len(normalized_symbol) < 6:
            logger.warning(f"无效的FX交易对: {symbol}")
            return None

        if use_cache:
            cached_data = self.storage.get_market_cache(self._cache_key(normalized_symbol))
            if cached_data and self._is_cache_valid(cached_data):
                return FXQuote.from_dict(cached_data)

        spot_rows = await self._fetch_spot_table()
        if not spot_rows:
            return None

        for row in spot_rows:
            if self._normalize_symbol(str(row.get("代码", ""))) != normalized_symbol:
                continue
            quote = self._row_to_quote(row)
            if quote:
                self.storage.save_market_cache(self._cache_key(normalized_symbol), quote.to_dict())
            return quote

        logger.info(f"未找到FX交易对: {normalized_symbol}")
        return None

    async def batch_get_quotes(self, symbols: List[str], use_cache: bool = True) -> Dict[str, Optional[FXQuote]]:
        """Batch get FX quotes with a single AkShare table fetch."""
        normalized_symbols = [self._normalize_symbol(symbol) for symbol in symbols if self._normalize_symbol(symbol)]
        results: Dict[str, Optional[FXQuote]] = {}
        missing_symbols: List[str] = []

        if use_cache:
            for symbol in normalized_symbols:
                cached_data = self.storage.get_market_cache(self._cache_key(symbol))
                if cached_data and self._is_cache_valid(cached_data):
                    results[symbol] = FXQuote.from_dict(cached_data)
                else:
                    missing_symbols.append(symbol)
        else:
            missing_symbols = normalized_symbols

        if not missing_symbols:
            return results

        spot_rows = await self._fetch_spot_table()
        if not spot_rows:
            for symbol in missing_symbols:
                results.setdefault(symbol, None)
            return results

        indexed_rows = {
            self._normalize_symbol(str(row.get("代码", ""))): row
            for row in spot_rows
        }

        for symbol in missing_symbols:
            row = indexed_rows.get(symbol)
            quote = self._row_to_quote(row) if row else None
            if quote:
                self.storage.save_market_cache(self._cache_key(symbol), quote.to_dict())
            results[symbol] = quote

        return results

    async def search_symbols(self, keyword: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Search FX symbols by code, name, or currency code."""
        normalized_keyword = self._normalize_symbol(keyword)
        plain_keyword = (keyword or "").strip().upper()
        if not plain_keyword:
            return []

        spot_rows = await self._fetch_spot_table()
        if not spot_rows:
            return []

        matches: List[Dict[str, Any]] = []
        for row in spot_rows:
            quote = self._row_to_quote(row)
            if not quote:
                continue

            haystacks = [
                quote.symbol,
                quote.name.upper(),
                quote.base_currency,
                quote.quote_currency,
                f"{quote.base_currency}/{quote.quote_currency}",
            ]

            if normalized_keyword and quote.symbol == normalized_keyword:
                score = 0
            elif any(plain_keyword in item for item in haystacks):
                score = 1
            else:
                continue

            matches.append({
                "symbol": quote.symbol,
                "name": quote.name,
                "base_currency": quote.base_currency,
                "quote_currency": quote.quote_currency,
                "mid_price": quote.mid_price,
                "score": score,
            })

        matches.sort(key=lambda item: (item["score"], item["symbol"]))
        deduped: List[Dict[str, Any]] = []
        seen_symbols = set()
        for item in matches:
            if item["symbol"] in seen_symbols:
                continue
            seen_symbols.add(item["symbol"])
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    async def get_history(self, symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Get normalized FX historical rows."""
        normalized_symbol = self._normalize_symbol(symbol)
        if len(normalized_symbol) < 6:
            return []

        rows = await self._fetch_hist_table(normalized_symbol)
        if not rows:
            return []

        normalized_rows: List[Dict[str, Any]] = []
        for row in rows[-limit:]:
            try:
                normalized_rows.append({
                    "date": str(row.get("日期", "")),
                    "symbol": self._normalize_symbol(str(row.get("代码", normalized_symbol))),
                    "name": str(row.get("名称", normalized_symbol)),
                    "open_price": float(row.get("今开", 0) or 0),
                    "close_price": float(row.get("最新价", 0) or 0),
                    "high_price": float(row.get("最高", 0) or 0),
                    "low_price": float(row.get("最低", 0) or 0),
                    "amplitude": float(row.get("振幅", 0) or 0),
                })
            except Exception as exc:
                logger.warning(f"标准化FX历史行情失败 {normalized_symbol}: {exc}")
        return normalized_rows

    def is_trading_time(self, target_time: Optional[datetime] = None) -> bool:
        """Simplified FX trading window: open on weekdays."""
        if target_time is None:
            target_time = datetime.now()
        return target_time.weekday() < 5

    def can_place_order(self, target_time: Optional[datetime] = None) -> tuple[bool, str]:
        if self.is_trading_time(target_time):
            return True, "FX交易时段"
        return False, "周末休市"

    def get_market_status(self, target_time: Optional[datetime] = None) -> Dict[str, Any]:
        if target_time is None:
            target_time = datetime.now()
        can_order, reason = self.can_place_order(target_time)
        return {
            "current_time": target_time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_trading_time": can_order,
            "can_place_order": can_order,
            "reason": reason,
            "cache_ttl": self._cache_ttl,
            "spread_ratio": self._spread_ratio,
        }

    def calculate_contract_notional(self, volume_lots: float, contract_size: float, market_price: float) -> float:
        if volume_lots <= 0 or contract_size <= 0 or market_price <= 0:
            return 0.0
        notional = volume_lots * contract_size * market_price
        return 0.0 if math.isnan(notional) or math.isinf(notional) else notional
