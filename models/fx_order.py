"""FX order business model."""
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional
import time
import uuid


class OrderSide(Enum):
    LONG = "long"
    SHORT = "short"


class OrderIntent(Enum):
    OPEN = "open"
    CLOSE = "close"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIAL_FILLED = "partial"
    LIQUIDATED = "liquidated"


class PriceType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class FXOrder:
    """Leveraged FX order."""

    order_id: str
    user_id: str
    symbol: str
    symbol_name: str
    side: OrderSide
    intent: OrderIntent
    price_type: PriceType
    leverage: float
    volume_lots: float
    contract_size: float
    requested_price: float
    trigger_price: Optional[float]
    fill_price: float
    filled_lots: float
    notional_value: float
    status: OrderStatus
    create_time: int
    update_time: int
    filled_time: Optional[int] = None

    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid.uuid4())
        if self.create_time == 0:
            self.create_time = int(time.time())
        if self.update_time == 0:
            self.update_time = int(time.time())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["side"] = self.side.value
        data["intent"] = self.intent.value
        data["price_type"] = self.price_type.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FXOrder":
        if isinstance(data.get("side"), str):
            data["side"] = OrderSide(data["side"])
        if isinstance(data.get("intent"), str):
            data["intent"] = OrderIntent(data["intent"])
        if isinstance(data.get("price_type"), str):
            data["price_type"] = PriceType(data["price_type"])
        if isinstance(data.get("status"), str):
            data["status"] = OrderStatus(data["status"])
        return cls(**data)

    def is_open_order(self) -> bool:
        return self.intent == OrderIntent.OPEN

    def is_close_order(self) -> bool:
        return self.intent == OrderIntent.CLOSE

    def is_long(self) -> bool:
        return self.side == OrderSide.LONG

    def is_short(self) -> bool:
        return self.side == OrderSide.SHORT

    def is_pending(self) -> bool:
        return self.status == OrderStatus.PENDING

    def fill_order(self, fill_price: float, filled_lots: Optional[float] = None):
        self.fill_price = fill_price
        self.filled_lots = self.volume_lots if filled_lots is None else filled_lots
        self.notional_value = self.filled_lots * self.contract_size * fill_price
        self.status = OrderStatus.FILLED if self.filled_lots >= self.volume_lots else OrderStatus.PARTIAL_FILLED
        self.filled_time = int(time.time())
        self.update_time = self.filled_time

    def cancel_order(self):
        self.status = OrderStatus.CANCELLED
        self.update_time = int(time.time())
