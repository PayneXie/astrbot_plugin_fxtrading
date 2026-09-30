## FX 业务模型定义

当前阶段先固定核心业务口径，后续引擎、命令和存储都按这份模型推进。

### 数据来源

- 实时行情：`akshare.forex_spot_em()`
- 历史行情：`akshare.forex_hist_em(symbol="USDCNH")`

当前从 `AkShare` 页面可确认：

- `forex_spot_em` 返回 `代码 / 名称 / 最新价 / 涨跌额 / 涨跌幅 / 今开 / 最高 / 最低 / 昨收`
- `forex_hist_em` 返回 `日期 / 代码 / 名称 / 今开 / 最新价 / 最高 / 最低 / 振幅`

### 账户模型

- 账户类型：`FXAccount`
- 账户字段：
  - `balance`：账户余额
  - `equity`：账户净值 = `balance + unrealized_pnl`
  - `gross_exposure`：总敞口
  - `max_leverage`：最大杠杆
- 不引入显式 `margin` / `used_margin` / `margin_level` 字段

### 风控与强平

- 支持做多、做空、杠杆交易
- 不做显式保证金占用展示
- 开仓限制采用杠杆上限：
  - `gross_exposure + new_notional <= equity * max_leverage`
- 强平规则：
  - 当 `equity <= 0` 时，触发强制平仓
  - 强平时默认平掉全部持仓

### 报价模型

- 报价类型：`FXQuote`
- 统一使用 `symbol` 表示交易对，例如 `EURUSD`、`USDJPY`
- 由于 `AkShare forex_spot_em` 当前以最新价为主，模型中保留 `mid_price`
- `bid/ask` 暂使用可配置的模拟点差从 `mid_price` 推导

### 订单模型

- 订单类型：`FXOrder`
- 支持：
  - `side`: `long / short`
  - `intent`: `open / close`
  - `price_type`: `market / limit`
- 数量单位采用 `lots`
- 保留 `contract_size` 字段，便于后续支持标准手、迷你手

### 持仓模型

- 持仓类型：`FXPosition`
- 核心字段：
  - `side`
  - `volume_lots`
  - `leverage`
  - `open_price`
  - `current_price`
  - `notional_value`
  - `unrealized_pnl`
- 浮盈亏计算采用简化公式：
  - `pnl = (market_price - open_price) * direction * volume_lots * contract_size`

### 当前约束

- 本阶段先完成 FX 核心模型迁移
- 旧股票模型、A 股规则、T+1、涨跌停、100 股整数倍等逻辑，后续分阶段移除
- 跨币种结算暂未落地，当前模型先保留 `base_currency / quote_currency`，后续在服务层补账户结算货币换算
