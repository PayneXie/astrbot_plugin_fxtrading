"""FX trading command handlers."""
from typing import AsyncGenerator, Dict, List, Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult

from ..services.fx_data import FXDataService
from ..services.fx_trading_engine import FXTradingEngine
from ..services.trade_coordinator import TradeCoordinator
from ..services.user_interaction import UserInteractionService


class TradingCommandHandlers:
    """FX交易命令处理器集合。"""

    def __init__(
        self,
        trade_coordinator: TradeCoordinator,
        user_interaction: UserInteractionService,
        fx_data_service: Optional[FXDataService] = None,
        fx_trading_engine: Optional[FXTradingEngine] = None,
    ):
        self.trade_coordinator = trade_coordinator
        self.user_interaction = user_interaction
        self.fx_data_service = fx_data_service or FXDataService(trade_coordinator.storage)
        self.fx_trading_engine = fx_trading_engine or FXTradingEngine(trade_coordinator.storage, self.fx_data_service)

    async def handle_market_buy(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """市价做多开仓。"""
        async for result in self._handle_fx_open(event, side="long", action_name="做多"):
            yield result

    async def handle_market_sell(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """市价做空开仓。"""
        async for result in self._handle_fx_open(event, side="short", action_name="做空"):
            yield result

    async def handle_close_position(self, event: AstrMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """平仓处理。"""
        user_id = self.trade_coordinator.get_isolated_user_id(event)
        if not self.trade_coordinator.storage.get_fx_account(user_id):
            yield MessageEventResult().message("❌ 您还未注册 FX 账户，请先使用 /fx注册")
            return

        params = event.message_str.strip().split()[1:]
        if not params:
            yield MessageEventResult().message("❌ 参数不足\n\n格式: /fx平仓 持仓ID [手数]\n例: /fx平仓 FXP-12345678 0.10")
            return

        position_id = params[0]
        volume_lots = None
        if len(params) >= 2:
            try:
                volume_lots = round(float(params[1]), 2)
                if volume_lots <= 0:
                    raise ValueError
            except ValueError:
                yield MessageEventResult().message("❌ 平仓手数格式错误，请输入大于0的数字")
                return

        position_data = self.trade_coordinator.storage.get_fx_position(user_id, position_id)
        if not position_data:
            yield MessageEventResult().message(f"❌ 未找到持仓 {position_id}")
            return

        symbol = position_data.get("symbol", "N/A")
        display_name = position_data.get("symbol_name", symbol)
        display_lots = volume_lots if volume_lots is not None else position_data.get("volume_lots", 0.0)
        estimated_fee_text = "未知"
        quote = await self.fx_data_service.get_quote(symbol, use_cache=False)
        if quote:
            close_price = quote.to_close_price(position_data.get("side", "long"))
            contract_size = float(position_data.get("contract_size", self.fx_trading_engine._default_contract_size()))
            close_notional = self.fx_data_service.calculate_contract_notional(display_lots, contract_size, close_price)
            estimated_fee_text = f"{self.fx_trading_engine.calculate_commission(close_notional):.2f}"
        confirmation = (
            "📋 即将执行 FX 平仓\n"
            f"交易对: {display_name} ({symbol})\n"
            f"持仓ID: {position_id}\n"
            f"手数: {display_lots:.2f} 手\n"
            f"类型: 市价平仓\n"
            f"手续费: {estimated_fee_text}(预估)"
        )

        confirmed, error_msg = await self.user_interaction.wait_for_trade_confirmation(
            event,
            {
                "confirmation_message": confirmation,
                "symbol_name": display_name,
                "symbol": symbol,
                "trade_type": "平仓",
                "volume_lots": display_lots,
                "price": None,
            },
        )
        if error_msg:
            yield MessageEventResult().message(error_msg)
            return
        if not confirmed:
            yield MessageEventResult().message("💭 交易已取消")
            return

        try:
            success, message, _ = await self.fx_trading_engine.place_close_order(
                user_id=user_id,
                position_id=position_id,
                volume_lots=volume_lots,
            )
            yield MessageEventResult().message(f"{'✅' if success else '❌'} {message}")
        except Exception as exc:
            logger.error(f"执行FX平仓失败: {exc}")
            yield MessageEventResult().message("❌ 平仓失败，请稍后重试")

    async def _handle_fx_open(
        self,
        event: AstrMessageEvent,
        side: str,
        action_name: str,
    ) -> AsyncGenerator[MessageEventResult, None]:
        """处理FX开仓。"""
        user_id = self.trade_coordinator.get_isolated_user_id(event)
        if not self.trade_coordinator.storage.get_fx_account(user_id):
            yield MessageEventResult().message("❌ 您还未注册 FX 账户，请先使用 /fx注册")
            return

        params = event.message_str.strip().split()[1:]
        parsed, error_msg = self._parse_fx_open_params(params)
        if error_msg:
            yield MessageEventResult().message(error_msg)
            return

        selected_symbol, error_msg = await self._select_fx_symbol(event, parsed["keyword"], action_name)
        if error_msg:
            yield MessageEventResult().message(error_msg)
            return
        if not selected_symbol:
            yield MessageEventResult().message("💭 交易已取消")
            return

        quote = await self.fx_data_service.get_quote(selected_symbol["symbol"], use_cache=False)
        if not quote:
            yield MessageEventResult().message("❌ 无法获取实时汇价，请稍后重试")
            return

        execution_price = quote.ask_price if side == "long" else quote.bid_price
        contract_size = self.fx_trading_engine._default_contract_size()
        estimated_notional = self.fx_data_service.calculate_contract_notional(
            parsed["volume_lots"],
            contract_size,
            execution_price,
        )
        estimated_commission = self.fx_trading_engine.calculate_commission(estimated_notional)
        confirmation = (
            "📋 即将执行 FX 开仓\n"
            f"交易对: {selected_symbol['name']} ({selected_symbol['symbol']})\n"
            f"方向: {'做多' if side == 'long' else '做空'}\n"
            f"手数: {parsed['volume_lots']:.2f} 手\n"
            f"杠杆: {parsed['leverage']:.2f}x\n"
            f"价格: {execution_price:.5f}(预估成交价)\n"
            f"手续费: {estimated_commission:.2f}(预估)"
        )

        confirmed, error_msg = await self.user_interaction.wait_for_trade_confirmation(
            event,
            {
                "confirmation_message": confirmation,
                "symbol_name": selected_symbol["name"],
                "symbol": selected_symbol["symbol"],
                "trade_type": action_name,
                "volume_lots": parsed["volume_lots"],
                "price": execution_price,
            },
        )
        if error_msg:
            yield MessageEventResult().message(error_msg)
            return
        if not confirmed:
            yield MessageEventResult().message("💭 交易已取消")
            return

        try:
            success, message, _, _ = await self.fx_trading_engine.place_open_order(
                user_id=user_id,
                symbol=selected_symbol["symbol"],
                side=side,
                volume_lots=parsed["volume_lots"],
                leverage=parsed["leverage"],
            )
            yield MessageEventResult().message(f"{'✅' if success else '❌'} {message}")
        except Exception as exc:
            logger.error(f"执行FX开仓失败: {exc}")
            yield MessageEventResult().message("❌ 开仓失败，请稍后重试")

    def _parse_fx_open_params(self, params: List[str]) -> tuple[Optional[Dict[str, float]], Optional[str]]:
        """解析FX开仓参数。"""
        if len(params) < 3:
            return None, "❌ 参数不足\n\n格式: /fx做多 交易对 手数 杠杆\n例: /fx做多 EURUSD 0.10 20"

        keyword = params[0]
        try:
            volume_lots = round(float(params[1]), 2)
            leverage = float(params[2])
        except ValueError:
            return None, "❌ 手数或杠杆格式错误，请输入数字"

        if volume_lots <= 0:
            return None, "❌ 手数必须大于0"
        if leverage <= 0:
            return None, "❌ 杠杆必须大于0"

        return {
            "keyword": keyword,
            "volume_lots": volume_lots,
            "leverage": leverage,
        }, None

    async def _select_fx_symbol(
        self,
        event: AstrMessageEvent,
        keyword: str,
        action_name: str,
    ) -> tuple[Optional[Dict[str, str]], Optional[str]]:
        """搜索并选择FX交易对。"""
        candidates = await self.fx_data_service.search_symbols(keyword)
        if not candidates:
            return None, f"❌ 未找到相关交易对: {keyword}"

        if len(candidates) == 1:
            return candidates[0], None

        prompt_lines = ["🔍 找到多个相关交易对，请选择:\n"]
        options = []
        for candidate in candidates[:5]:
            options.append(f"{candidate['name']} ({candidate['symbol']})")
            prompt_lines.append(
                f"{len(options)}. {candidate['name']} ({candidate['symbol']}) "
                f"[{candidate['base_currency']}/{candidate['quote_currency']}]"
            )

        selected_index, error_msg = await self.user_interaction.wait_for_choice_selection(
            event,
            "\n".join(prompt_lines) + f"\n\n💡 请选择用于{action_name}的交易对",
            options,
        )
        if error_msg:
            return None, error_msg
        if selected_index is None:
            return None, "用户取消选择"
        return candidates[selected_index], None
