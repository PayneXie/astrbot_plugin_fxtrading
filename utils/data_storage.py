"""FX plugin data storage."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger
from astrbot.api.star import StarTools


class DataStorage:
    """Persist FX accounts, orders, positions, cache, and plugin config."""

    def __init__(self, plugin_name: str = "fxtrading", plugin_config=None):
        self.plugin_name = plugin_name
        self.plugin_config = plugin_config
        self.data_dir = StarTools.get_data_dir(plugin_name)
        self._ensure_data_structure()

    def _ensure_data_structure(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "fx_accounts.json": {},
            "fx_orders.json": {},
            "fx_positions.json": {},
            "market_data_cache.json": {},
            "config.json": {},
            "order_counter.json": {"current_number": 0},
        }
        for filename, default_data in files.items():
            file_path = self.data_dir / filename
            if not file_path.exists():
                self._save_json(filename, default_data)

    def _get_file_path(self, filename: str) -> Path:
        return self.data_dir / filename

    def _load_json(self, filename: str) -> Dict[str, Any]:
        file_path = self._get_file_path(filename)
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
        except Exception as exc:
            logger.error(f"加载文件失败 {filename}: {exc}")
        return {}

    def _save_json(self, filename: str, data: Dict[str, Any]):
        file_path = self._get_file_path(filename)
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"保存文件失败 {filename}: {exc}")

    def get_fx_account(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._load_json("fx_accounts.json").get(user_id)

    def save_fx_account(self, user_id: str, account_data: Dict[str, Any]):
        accounts = self._load_json("fx_accounts.json")
        accounts[user_id] = account_data
        self._save_json("fx_accounts.json", accounts)

    def get_all_fx_accounts(self) -> Dict[str, Any]:
        return self._load_json("fx_accounts.json")

    def delete_fx_account(self, user_id: str):
        accounts = self._load_json("fx_accounts.json")
        if user_id in accounts:
            del accounts[user_id]
            self._save_json("fx_accounts.json", accounts)

    def get_next_order_number(self) -> str:
        counter_data = self._load_json("order_counter.json")
        next_number = int(counter_data.get("current_number", 0)) + 1
        if next_number > 99999:
            next_number = 1
        counter_data["current_number"] = next_number
        self._save_json("order_counter.json", counter_data)
        return f"{next_number:05d}"

    def get_fx_orders(self, user_id: str = None) -> List[Dict[str, Any]]:
        orders = self._load_json("fx_orders.json")
        values = list(orders.values())
        if user_id:
            values = [order for order in values if order.get("user_id") == user_id]
        return values

    def save_fx_order(self, order_id: str, order_data: Dict[str, Any]):
        orders = self._load_json("fx_orders.json")
        orders[order_id] = order_data
        self._save_json("fx_orders.json", orders)

    def get_fx_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self._load_json("fx_orders.json").get(order_id)

    def delete_fx_order(self, order_id: str):
        orders = self._load_json("fx_orders.json")
        if order_id in orders:
            del orders[order_id]
            self._save_json("fx_orders.json", orders)

    def get_user_fx_order_history(self, user_id: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        orders = self._load_json("fx_orders.json")
        user_orders = [
            order for order in orders.values()
            if order.get("user_id") == user_id and order.get("status") in ["filled", "partial", "liquidated"]
        ]
        user_orders.sort(key=lambda item: item.get("update_time", 0), reverse=True)

        total_count = len(user_orders)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        return {
            "orders": user_orders[start_index:end_index],
            "total_count": total_count,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }

    def get_fx_positions(self, user_id: str) -> List[Dict[str, Any]]:
        positions = self._load_json("fx_positions.json")
        return list(positions.get(user_id, {}).values())

    def save_fx_position(self, user_id: str, position_id: str, position_data: Dict[str, Any]):
        positions = self._load_json("fx_positions.json")
        positions.setdefault(user_id, {})
        positions[user_id][position_id] = position_data
        self._save_json("fx_positions.json", positions)

    def get_fx_position(self, user_id: str, position_id: str) -> Optional[Dict[str, Any]]:
        return self._load_json("fx_positions.json").get(user_id, {}).get(position_id)

    def delete_fx_position(self, user_id: str, position_id: str):
        positions = self._load_json("fx_positions.json")
        if user_id in positions and position_id in positions[user_id]:
            del positions[user_id][position_id]
            if not positions[user_id]:
                del positions[user_id]
            self._save_json("fx_positions.json", positions)

    def get_market_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        return self._load_json("market_data_cache.json").get(cache_key)

    def save_market_cache(self, cache_key: str, market_data: Dict[str, Any]):
        cache = self._load_json("market_data_cache.json")
        cache[cache_key] = market_data
        self._save_json("market_data_cache.json", cache)

    def clear_market_cache(self):
        self._save_json("market_data_cache.json", {})

    def get_config(self) -> Dict[str, Any]:
        return self._load_json("config.json")

    def save_config(self, config: Dict[str, Any]):
        self._save_json("config.json", config)

    def get_plugin_config_value(self, key: str, default=None):
        if self.plugin_config and hasattr(self.plugin_config, "get"):
            return self.plugin_config.get(key, default)
        return self.get_config().get(key, default)
