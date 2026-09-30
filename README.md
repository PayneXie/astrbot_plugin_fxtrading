# AstrBot FX Trading Plugin

一个基于 AstrBot 的模拟 FX 交易插件，使用 `AkShare` 提供汇率数据，支持：

- 实时汇价查询
- 做多 / 做空
- 杠杆开仓
- 市价平仓
- 真实 FX `24/5` 交易时间
- 成交手续费
- 账户净值与浮盈亏刷新
- 当净值 `<= 0` 时强制平仓
- 群内排行榜与历史订单

当前版本定位为 **实时成交的 FX 模拟盘**，不包含限价挂单、撤单、显式保证金字段。

## 功能概览

### 交易模型

- 数据源：`AkShare`
- 标的：外汇交易对，例如 `EURUSD`、`USDJPY`
- 交易方向：做多、做空
- 成交方式：仅支持实时成交
- 交易时间：按 UTC 口径执行周度开盘、周度收盘和日常维护窗口
- 成本：开仓、平仓均收取手续费
- 风控方式：按账户净值判断，净值 `<= 0` 时触发强制平仓

### 账户模型

账户核心字段：

- `balance`：账户余额
- `equity`：账户净值
- `realized_pnl`：已实现盈亏
- `unrealized_pnl`：浮动盈亏
- `gross_exposure`：总敞口
- `max_leverage`：最大杠杆
- `total_fees`：累计手续费

### 行情模型

插件从 `AkShare forex_spot_em` 获取实时汇率，并基于中间价推导模拟：

- `bid_price`
- `ask_price`
- `spread`

其中：

- 做多开仓按 `ask` 成交
- 做空开仓按 `bid` 成交
- 做多平仓按 `bid` 成交
- 做空平仓按 `ask` 成交

## 命令说明

### 用户命令

```text
/fx注册
/fx账户
/fx汇价 EURUSD
/fx排行
/fx历史
/fx
```

### 交易命令

```text
/fx买入 EURUSD 0.10 20
/fx卖出 EURUSD 0.10 20
/fx平仓 FXP-12345678
/fx平仓 FXP-12345678 0.05
```

说明：

- `/fx买入`：市价做多开仓
- `/fx卖出`：市价做空开仓
- `/fx平仓`：按持仓 ID 市价平仓，可选部分平仓

### 管理员命令

```text
/fx状态
```

用于查看后台风控轮询状态。

## 配置项

插件当前支持这些主要配置：

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `monitor_interval` | FX 风控轮询间隔（秒） | `15` |
| `initial_balance` | 注册初始资金 | `1000000` |
| `fx_quote_cache_seconds` | 行情缓存秒数 | `15` |
| `fx_spread_ratio` | 模拟点差比例 | `0.0002` |
| `fx_default_max_leverage` | 默认最大杠杆 | `20` |
| `fx_contract_size` | 每手默认合约规模 | `100000` |
| `fx_commission_rate` | 单边手续费率 | `0.000035` |
| `fx_min_commission` | 单边最低手续费 | `0` |
| `fx_week_open_utc_hour/minute` | 周度开盘 UTC 时间 | `22:05` |
| `fx_week_close_utc_hour/minute` | 周度收盘 UTC 时间 | `21:55` |
| `fx_daily_break_start_utc_hour/minute` | 维护开始 UTC 时间 | `21:59` |
| `fx_daily_break_end_utc_hour/minute` | 维护结束 UTC 时间 | `22:05` |

## 项目结构

```text
.
├── main.py
├── handlers/
├── models/
├── services/
├── utils/
├── FX_MODEL.md
├── metadata.yaml
└── _conf_schema.json
```

其中：

- `handlers/`：AstrBot 命令入口
- `services/fx_data.py`：AkShare 行情接入
- `services/fx_trading_engine.py`：开仓、平仓、强平
- `services/order_monitor.py`：后台净值刷新与强平扫描
- `utils/data_storage.py`：FX 账户、订单、持仓存储

## 安装

1. 将插件放入 AstrBot 插件目录
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 重载或重启 AstrBot

## 当前实现边界

这版已经能覆盖你当前提出的核心需求，但仍有这些实现边界：

- 还没有隔夜利息、滑点、手续费分层等更细的经纪商规则
- 还没有精确到夏令时切换的交易时段模板，当前默认使用一组 UTC 固定窗口
- 没有止盈止损命令入口，虽然模型字段已预留

## 开源协议

本项目沿用仓库中的 [AGPL-3.0](LICENSE) 许可证。
