"""FX trading coordinator."""
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

from ..utils.data_storage import DataStorage
from .fx_data import FXDataService
from .fx_trading_engine import FXTradingEngine


class TradeCoordinator:
    """Coordinate FX-specific shared workflow helpers."""

    def __init__(self, storage: DataStorage, fx_data_service: FXDataService | None = None):
        self.storage = storage
        self.fx_data_service = fx_data_service or FXDataService(storage)
        self.fx_trading_engine = FXTradingEngine(storage, self.fx_data_service)

    def get_isolated_user_id(self, event: AstrMessageEvent) -> str:
        """Build a per-platform, per-session user key."""
        platform_name = event.get_platform_name()
        sender_id = event.get_sender_id()
        session_id = event.get_session_id()
        return f"{platform_name}:{sender_id}:{session_id}"

    async def update_user_assets_if_needed(self, user_id: str):
        """Refresh an FX account snapshot before responding."""
        try:
            if self.storage.get_fx_account(user_id):
                await self.fx_trading_engine.update_account_state(user_id)
        except Exception as exc:
            logger.error(f"更新FX账户状态失败: {exc}")
