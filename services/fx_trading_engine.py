"""FX trading engine."""
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger

from ..models.fx_account import FXAccount
from ..models.fx_order import FXOrder, OrderIntent, OrderSide, OrderStatus, PriceType
from ..models.fx_position import FXPosition
from ..utils.data_storage import DataStorage
from .fx_data import FXDataService


class FXTradingEngine:
    """Core FX trading and liquidation logic."""

    def __init__(self, storage: DataStorage, fx_data_service: Optional[FXDataService] = None):
        self.storage = storage
        self.fx_data_service = fx_data_service or FXDataService(storage)

    def _default_contract_size(self) -> float:
        return float(self.storage.get_plugin_config_value("fx_contract_size", 100000.0))

    def _normalize_lots(self, volume_lots: float) -> float:
        return round(float(volume_lots), 2)

    def _new_position_id(self) -> str:
        return f"FXP-{str(uuid.uuid4())[:8]}"

    def _load_account(self, user_id: str) -> Optional[FXAccount]:
        account_data = self.storage.get_fx_account(user_id)
        if not account_data:
            return None
        return FXAccount.from_dict(account_data)

    def _load_position(self, user_id: str, position_id: str) -> Optional[FXPosition]:
        position_data = self.storage.get_fx_position(user_id, position_id)
        if not position_data:
            return None
        return FXPosition.from_dict(position_data)

    async def place_open_order(
        self,
        user_id: str,
        symbol: str,
        side: str,
        volume_lots: float,
        leverage: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Tuple[bool, str, Optional[FXOrder], Optional[FXPosition]]:
        """Open a leveraged FX position with market execution."""
        can_trade, reason = self.fx_data_service.can_place_order()
        if not can_trade:
            return False, reason, None, None

        account = self._load_account(user_id)
        if not account:
            return False, "用户未注册FX账户，请先使用 /fx注册", None, None

        await self.update_account_state(user_id, enforce_liquidation=False)
        account = self._load_account(user_id)
        if not account or account.equity <= 0:
            return False, "账户净值不足，无法开仓", None, None

        normalized_lots = self._normalize_lots(volume_lots)
        if normalized_lots <= 0:
            return False, "下单手数必须大于0", None, None

        if leverage <= 0 or leverage > account.max_leverage:
            return False, f"杠杆超出范围，当前账户最大杠杆为 {account.max_leverage:.2f}x", None, None

        quote = await self.fx_data_service.get_quote(symbol, use_cache=False)
        if not quote:
            return False, f"无法获取交易对 {symbol} 的行情", None, None

        order_side = OrderSide(side)
        fill_price = quote.to_open_price(order_side.value)
        contract_size = self._default_contract_size()

        order = FXOrder(
            order_id=self.storage.get_next_order_number(),
            user_id=user_id,
            symbol=quote.symbol,
            symbol_name=quote.name,
            side=order_side,
            intent=OrderIntent.OPEN,
            price_type=PriceType.MARKET,
            leverage=float(leverage),
            volume_lots=normalized_lots,
            contract_size=contract_size,
            requested_price=float(fill_price),
            trigger_price=None,
            fill_price=0.0,
            filled_lots=0.0,
            notional_value=0.0,
            status=OrderStatus.PENDING,
            create_time=0,
            update_time=0,
        )

        notional = self.fx_data_service.calculate_contract_notional(normalized_lots, contract_size, fill_price)
        if not account.can_open_position(notional):
            return False, "杠杆敞口超限，无法开仓", None, None

        position = FXPosition(
            position_id=self._new_position_id(),
            user_id=user_id,
            symbol=quote.symbol,
            symbol_name=quote.name,
            side=order_side,
            leverage=float(leverage),
            volume_lots=normalized_lots,
            contract_size=contract_size,
            base_currency=quote.base_currency,
            quote_currency=quote.quote_currency,
            open_price=fill_price,
            current_price=quote.mid_price,
            notional_value=notional,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            stop_loss=stop_loss,
            take_profit=take_profit,
            open_time=int(time.time()),
            update_time=int(time.time()),
        )
        position.update_market_price(quote.to_close_price(order_side.value))

        order.fill_order(fill_price)
        self.storage.save_fx_order(order.order_id, order.to_dict())
        self.storage.save_fx_position(user_id, position.position_id, position.to_dict())
        await self.update_account_state(user_id)

        return True, (
            f"开仓成功：{quote.name}({quote.symbol}) "
            f"{'做多' if order_side == OrderSide.LONG else '做空'} "
            f"{normalized_lots:.2f}手，成交价 {fill_price:.5f}"
        ), order, position

    async def place_close_order(
        self,
        user_id: str,
        position_id: str,
        volume_lots: Optional[float] = None,
    ) -> Tuple[bool, str, Optional[FXOrder]]:
        """Close an existing FX position with market execution."""
        can_trade, reason = self.fx_data_service.can_place_order()
        if not can_trade:
            return False, reason, None

        account = self._load_account(user_id)
        if not account:
            return False, "用户未注册FX账户", None

        position = self._load_position(user_id, position_id)
        if not position:
            return False, "持仓不存在", None

        close_lots = self._normalize_lots(volume_lots if volume_lots is not None else position.volume_lots)
        if close_lots <= 0 or close_lots > position.volume_lots:
            return False, "平仓手数无效", None

        quote = await self.fx_data_service.get_quote(position.symbol, use_cache=False)
        if not quote:
            return False, f"无法获取交易对 {position.symbol} 的行情", None

        fill_price = quote.to_close_price(position.side.value)
        order = FXOrder(
            order_id=self.storage.get_next_order_number(),
            user_id=user_id,
            symbol=position.symbol,
            symbol_name=position.symbol_name,
            side=position.side,
            intent=OrderIntent.CLOSE,
            price_type=PriceType.MARKET,
            leverage=position.leverage,
            volume_lots=close_lots,
            contract_size=position.contract_size,
            requested_price=float(fill_price),
            trigger_price=None,
            fill_price=0.0,
            filled_lots=0.0,
            notional_value=0.0,
            status=OrderStatus.PENDING,
            create_time=0,
            update_time=0,
        )

        await self._execute_close_order(account, position, order, fill_price)
        return True, (
            f"平仓成功：{position.symbol_name}({position.symbol}) "
            f"{close_lots:.2f}手，成交价 {fill_price:.5f}"
        ), order

    async def update_account_state(self, user_id: str, enforce_liquidation: bool = True) -> Optional[FXAccount]:
        """Refresh prices, floating PnL, exposure, and optionally liquidate."""
        account = self._load_account(user_id)
        if not account:
            return None

        positions = [FXPosition.from_dict(item) for item in self.storage.get_fx_positions(user_id)]
        if not positions:
            account.update_exposure(0.0)
            account.update_equity(0.0)
            self.storage.save_fx_account(user_id, account.to_dict())
            return account

        quotes = await self.fx_data_service.batch_get_quotes([position.symbol for position in positions], use_cache=False)

        total_unrealized = 0.0
        total_exposure = 0.0
        for position in positions:
            quote = quotes.get(position.symbol)
            if not quote:
                # Keep the last known risk state when fresh quotes are unavailable.
                total_unrealized += position.unrealized_pnl
                total_exposure += position.notional_value
                continue

            market_price = quote.to_close_price(position.side.value)
            position.update_market_price(market_price)
            total_unrealized += position.unrealized_pnl
            total_exposure += position.notional_value
            self.storage.save_fx_position(user_id, position.position_id, position.to_dict())

        account.update_exposure(total_exposure)
        account.update_equity(total_unrealized)
        self.storage.save_fx_account(user_id, account.to_dict())

        if enforce_liquidation and account.should_force_liquidate():
            await self.force_liquidate_account(user_id, "账户净值小于等于0")
            return self._load_account(user_id)

        return account

    async def force_liquidate_account(self, user_id: str, reason: str) -> Tuple[bool, str]:
        """Force close all FX positions for an account."""
        account = self._load_account(user_id)
        if not account:
            return False, "FX账户不存在"

        positions = [FXPosition.from_dict(item) for item in self.storage.get_fx_positions(user_id)]
        if not positions:
            return True, "无持仓需要强平"

        quotes = await self.fx_data_service.batch_get_quotes([position.symbol for position in positions], use_cache=False)
        liquidated_count = 0

        for position in positions:
            quote = quotes.get(position.symbol)
            if not quote:
                logger.warning(f"强平时无法获取行情: {position.symbol}")
                continue

            fill_price = quote.to_close_price(position.side.value)
            order = FXOrder(
                order_id=self.storage.get_next_order_number(),
                user_id=user_id,
                symbol=position.symbol,
                symbol_name=position.symbol_name,
                side=position.side,
                intent=OrderIntent.CLOSE,
                price_type=PriceType.MARKET,
                leverage=position.leverage,
                volume_lots=position.volume_lots,
                contract_size=position.contract_size,
                requested_price=fill_price,
                trigger_price=None,
                fill_price=0.0,
                filled_lots=0.0,
                notional_value=0.0,
                status=OrderStatus.PENDING,
                create_time=0,
                update_time=0,
            )

            await self._execute_close_order(account, position, order, fill_price, liquidation_reason=reason)
            liquidated_count += 1

        await self.update_account_state(user_id, enforce_liquidation=False)
        return True, f"已强制平仓 {liquidated_count} 笔持仓"

    async def get_account_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a snapshot summary for an FX account."""
        account = await self.update_account_state(user_id)
        if not account:
            return {}

        positions = self.storage.get_fx_positions(user_id)
        orders = self.storage.get_fx_orders(user_id)
        return {
            "account": account.to_dict(),
            "positions": positions,
            "orders": orders,
        }

    async def scan_all_accounts_for_liquidation(self) -> int:
        """Refresh all FX accounts and apply liquidation if needed."""
        liquidated_accounts = 0
        for user_id in self.storage.get_all_fx_accounts().keys():
            before_positions = len(self.storage.get_fx_positions(user_id))
            await self.update_account_state(user_id, enforce_liquidation=True)
            after_positions = len(self.storage.get_fx_positions(user_id))
            if before_positions > 0 and after_positions == 0:
                liquidated_accounts += 1
        return liquidated_accounts

    async def _execute_close_order(
        self,
        account: FXAccount,
        position: FXPosition,
        order: FXOrder,
        fill_price: float,
        liquidation_reason: Optional[str] = None,
    ):
        """Close all or part of a position and realize PnL."""
        close_lots = min(order.volume_lots, position.volume_lots)
        realized_pnl = (fill_price - position.open_price) * position.direction_multiplier()
        realized_pnl *= close_lots * position.contract_size

        order.fill_order(fill_price, filled_lots=close_lots)
        if liquidation_reason:
            order.status = OrderStatus.LIQUIDATED
            order.update_time = int(time.time())

        account.apply_realized_pnl(realized_pnl)

        remaining_lots = round(position.volume_lots - close_lots, 2)
        if remaining_lots <= 0:
            self.storage.delete_fx_position(position.user_id, position.position_id)
        else:
            position.volume_lots = remaining_lots
            position.realized_pnl += realized_pnl
            position.update_market_price(fill_price)
            self.storage.save_fx_position(position.user_id, position.position_id, position.to_dict())

        self.storage.save_fx_order(order.order_id, order.to_dict())
        self.storage.save_fx_account(account.user_id, account.to_dict())
        await self.update_account_state(account.user_id, enforce_liquidation=False)
