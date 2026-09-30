"""FX account business model."""
from dataclasses import asdict, dataclass
from typing import Any, Dict
import time


@dataclass
class FXAccount:
    """Leveraged FX account without explicit margin fields."""

    user_id: str
    username: str
    base_currency: str
    balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    gross_exposure: float
    max_leverage: float
    liquidation_enabled: bool
    register_time: int
    last_login: int
    total_fees: float = 0.0

    def __post_init__(self):
        if self.register_time == 0:
            self.register_time = int(time.time())
        if self.last_login == 0:
            self.last_login = int(time.time())
        if self.equity == 0:
            self.equity = self.balance + self.unrealized_pnl

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FXAccount":
        normalized = dict(data)
        normalized.setdefault("total_fees", 0.0)
        return cls(**normalized)

    def update_login_time(self):
        self.last_login = int(time.time())

    def update_equity(self, unrealized_pnl: float):
        self.unrealized_pnl = unrealized_pnl
        self.equity = self.balance + unrealized_pnl

    def update_exposure(self, gross_exposure: float):
        self.gross_exposure = max(gross_exposure, 0.0)

    def apply_realized_pnl(self, realized_pnl: float):
        self.realized_pnl += realized_pnl
        self.balance += realized_pnl
        self.equity = self.balance + self.unrealized_pnl

    def apply_fee(self, fee_amount: float):
        fee = max(float(fee_amount), 0.0)
        if fee == 0:
            return
        self.total_fees += fee
        self.realized_pnl -= fee
        self.balance -= fee
        self.equity = self.balance + self.unrealized_pnl

    def can_open_position(self, additional_notional: float) -> bool:
        if additional_notional <= 0 or self.equity <= 0 or self.max_leverage <= 0:
            return False
        return (self.gross_exposure + additional_notional) <= (self.equity * self.max_leverage)

    def should_force_liquidate(self) -> bool:
        return self.liquidation_enabled and self.equity <= 0
