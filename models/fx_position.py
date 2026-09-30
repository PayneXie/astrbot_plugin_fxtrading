"""FX position business model."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
import time

from .fx_order import OrderSide


@dataclass
class FXPosition:
    """Open leveraged FX position."""

    position_id: str
    user_id: str
    symbol: str
    symbol_name: str
    side: OrderSide
    leverage: float
    volume_lots: float
    contract_size: float
    base_currency: str
    quote_currency: str
    open_price: float
    current_price: float
    notional_value: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    open_time: int
    update_time: int

    def __post_init__(self):
        if self.open_time == 0:
            self.open_time = int(time.time())
        if self.update_time == 0:
            self.update_time = int(time.time())
        if self.notional_value == 0 and self.current_price > 0:
            self.notional_value = self.calculate_notional(self.current_price)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["side"] = self.side.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FXPosition":
        if isinstance(data.get("side"), str):
            data["side"] = OrderSide(data["side"])
        return cls(**data)

    def direction_multiplier(self) -> int:
        return 1 if self.side == OrderSide.LONG else -1

    def calculate_notional(self, market_price: Optional[float] = None) -> float:
        reference_price = self.current_price if market_price is None else market_price
        return self.volume_lots * self.contract_size * reference_price

    def calculate_unrealized_pnl(self, market_price: float) -> float:
        price_diff = (market_price - self.open_price) * self.direction_multiplier()
        return price_diff * self.volume_lots * self.contract_size

    def update_market_price(self, market_price: float):
        self.current_price = market_price
        self.notional_value = self.calculate_notional(market_price)
        self.unrealized_pnl = self.calculate_unrealized_pnl(market_price)
        self.update_time = int(time.time())

    def should_take_profit(self, market_price: float) -> bool:
        if self.take_profit is None:
            return False
        if self.side == OrderSide.LONG:
            return market_price >= self.take_profit
        return market_price <= self.take_profit

    def should_stop_loss(self, market_price: float) -> bool:
        if self.stop_loss is None:
            return False
        if self.side == OrderSide.LONG:
            return market_price <= self.stop_loss
        return market_price >= self.stop_loss
