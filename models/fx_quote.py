"""FX quote business model."""
from dataclasses import asdict, dataclass
from typing import Any, Dict
import time


def _split_symbol(symbol: str) -> tuple[str, str]:
    normalized = (symbol or "").upper().strip()
    if len(normalized) >= 6:
        return normalized[:3], normalized[3:6]
    return normalized, ""


@dataclass
class FXQuote:
    """Real-time FX quote with synthetic bid/ask support."""

    symbol: str
    name: str
    base_currency: str
    quote_currency: str
    mid_price: float
    bid_price: float
    ask_price: float
    open_price: float
    high_price: float
    low_price: float
    prev_close: float
    change_amount: float
    change_percent: float
    spread_ratio: float
    source: str
    update_time: int

    def __post_init__(self):
        if self.update_time == 0:
            self.update_time = int(time.time())
        if not self.base_currency or not self.quote_currency:
            self.base_currency, self.quote_currency = _split_symbol(self.symbol)
        if self.mid_price > 0 and (self.bid_price <= 0 or self.ask_price <= 0):
            half_spread = self.mid_price * max(self.spread_ratio, 0.0) / 2
            self.bid_price = self.mid_price - half_spread
            self.ask_price = self.mid_price + half_spread

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FXQuote":
        return cls(**data)

    @classmethod
    def from_akshare_spot(
        cls,
        raw_data: Dict[str, Any],
        spread_ratio: float = 0.0002,
        source: str = "akshare.forex_spot_em",
    ) -> "FXQuote":
        symbol = str(raw_data.get("代码", "")).upper().strip()
        base_currency, quote_currency = _split_symbol(symbol)
        mid_price = float(raw_data.get("最新价", 0) or 0)
        return cls(
            symbol=symbol,
            name=str(raw_data.get("名称", symbol)),
            base_currency=base_currency,
            quote_currency=quote_currency,
            mid_price=mid_price,
            bid_price=0,
            ask_price=0,
            open_price=float(raw_data.get("今开", mid_price) or mid_price),
            high_price=float(raw_data.get("最高", mid_price) or mid_price),
            low_price=float(raw_data.get("最低", mid_price) or mid_price),
            prev_close=float(raw_data.get("昨收", mid_price) or mid_price),
            change_amount=float(raw_data.get("涨跌额", 0) or 0),
            change_percent=float(raw_data.get("涨跌幅", 0) or 0),
            spread_ratio=spread_ratio,
            source=source,
            update_time=int(time.time()),
        )

    def to_open_price(self, side: str) -> float:
        return self.ask_price if side == "long" else self.bid_price

    def to_close_price(self, side: str) -> float:
        return self.bid_price if side == "long" else self.ask_price

    def spread(self) -> float:
        return max(self.ask_price - self.bid_price, 0.0)
