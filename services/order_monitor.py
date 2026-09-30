"""FX risk monitor service."""
import asyncio
import time
from typing import Any, Dict

from astrbot.api import logger

from ..utils.data_storage import DataStorage
from .fx_data import FXDataService
from .fx_trading_engine import FXTradingEngine


class OrderMonitorService:
    """Periodic FX account refresh and liquidation scanner."""

    def __init__(self, storage: DataStorage):
        self.storage = storage
        self.fx_data_service = FXDataService(storage)
        self.fx_trading_engine = FXTradingEngine(storage, self.fx_data_service)
        self._running = False
        self._task = None
        self._paused = False
        self._last_poll_time = None
        self._last_connectivity_status = True
        self._next_poll_time = None
        self._connectivity_success_count = 0
        self._connectivity_total_count = 0

    async def start_monitoring(self):
        """Start the background monitor loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("FX风控监控服务已启动")

    async def stop_monitoring(self):
        """Stop the background monitor loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("FX风控监控服务已停止")

    async def _monitor_loop(self):
        """Poll FX accounts and trigger liquidations when needed."""
        while self._running:
            try:
                interval = self.storage.get_plugin_config_value("monitor_interval", 15)
                if interval <= 0:
                    if not self._paused:
                        logger.info("轮询间隔设为0，暂停FX风控监控")
                        self._paused = True
                    await asyncio.sleep(5)
                    continue

                if self._paused:
                    logger.info(f"轮询间隔设为{interval}秒，恢复FX风控监控")
                    self._paused = False

                self._last_poll_time = time.time()
                self._next_poll_time = self._last_poll_time + interval

                accounts = self.storage.get_all_fx_accounts()
                if accounts and self.fx_data_service.is_trading_time():
                    self._connectivity_total_count += 1
                    await self.fx_trading_engine.scan_all_accounts_for_liquidation()
                    self._connectivity_success_count += 1
                    self._last_connectivity_status = True
                else:
                    self._last_connectivity_status = True

                await asyncio.sleep(interval)
            except Exception as exc:
                self._connectivity_total_count += 1
                self._last_connectivity_status = False
                logger.error(f"FX监控循环错误: {exc}")
                await asyncio.sleep(5)

    def get_monitor_status(self) -> Dict[str, Any]:
        """Return monitor status for the admin command."""
        current_time = time.time()
        connectivity_rate = 0.0
        if self._connectivity_total_count > 0:
            connectivity_rate = (self._connectivity_success_count / self._connectivity_total_count) * 100

        current_interval = self.storage.get_plugin_config_value("monitor_interval", 15)

        def format_time(timestamp):
            if timestamp is None:
                return "未开始"
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        next_poll_display = "未知"
        if self._next_poll_time:
            next_poll_display = format_time(self._next_poll_time) if self._next_poll_time > current_time else "即将轮询"

        return {
            "is_running": self._running,
            "is_paused": self._paused,
            "current_interval": current_interval,
            "last_poll_time": format_time(self._last_poll_time),
            "last_connectivity_status": self._last_connectivity_status,
            "connectivity_rate": connectivity_rate,
            "connectivity_stats": f"{self._connectivity_success_count}/{self._connectivity_total_count}",
            "next_poll_time": next_poll_display,
            "is_fx_trading_time": self.fx_data_service.is_trading_time(),
        }
