# 技术笔记

记录项目开发过程中的关键 Q&A，供后续查阅。

---

## 1. 交易执行机制

### 1.1 schedule 函数参数说明

```python
schedule(schedule_func=annual_rebalance, date_rule='1m', time_rule='09:35:00')
```

| 参数 | 说明 |
|------|------|
| `schedule_func` | 定时执行的策略函数 |
| `date_rule` | 执行频率：`'1d'` 每天、`'1w'` 每周、`'1m'` 每月 |
| `time_rule` | 执行时间，格式 `%H:%M:%S` |

注意：`'1w'` 和 `'1m'` 仅用于回测，不能用于仿真和实盘。

### 1.2 time_rule 与成交价的关系

**结论**：`time_rule` 只决定策略逻辑何时运行，**不影响成交价**。

- `time_rule='09:35:00'`：策略在 09:35 运行
- 成交价由 `backtest_match_mode` 决定，与 `time_rule` 无关

对于日线频率 + 默认撮合模式（mode=0），无论 `time_rule` 设为 09:30 还是 15:00，成交价都是次日开盘价。

### 1.3 backtest_match_mode 两种模式对比

在 `run()` 中设置 `backtest_match_mode` 参数：

| 模式 | 成交价 | 说明 |
|------|--------|------|
| `0`（默认） | 下一根 bar 开盘价 | 延时撮合，更保守，模拟执行时滞 |
| `1` | 当前 bar 收盘价 | 实时撮合，更激进，假设能精确在收盘成交 |

**为什么默认用次日开盘价？**

不是因为"未来数据未知"（回测模式下所有历史价格已知），而是为了**模拟真实交易的执行时滞**：

```
09:35 决策下单
    ↓
T+1日 开盘价成交（最早能成交的价格）
```

如果用当日收盘价（15:00），从 09:35 到 15:00 有 5.5 小时时滞，对策略回测不够真实。

### 1.4 "下一根 bar"的含义

当 `schedule` 的 `date_rule='1m'`（每月调仓）时：

```
2005-06-01 09:35:00  schedule 触发 annual_rebalance
    ↓
    执行策略逻辑（获取数据、选股、下单）
    ↓
order_target_percent() 下单
    ↓
成交价 = 2005-06-02 的后复权开盘价（下一个交易日）
```

如果未订阅行情，gm SDK 默认使用日线 bar，"下一根 bar"就是下一个交易日。

---

## 2. 价格与复权

### 2.1 ADJUST_POST 对 VWAP 的影响

在 `run()` 中设置 `backtest_adjust=ADJUST_POST`（后复权），会影响以下数据：

| 数据类型 | 是否受 ADJUST_POST 影响 |
|----------|------------------------|
| 行情数据（open/high/low/close） | 是，使用后复权价 |
| 市价单成交价 | 是，使用后复权价 |
| `pos.vwap`（持仓均价） | **是**，基于后复权成交价计算 |
| `pos.market_value`（持仓市值） | 是，基于后复权价计算 |

gm SDK 官方确认：

> 回测模式下市价单，是复权还是不复权价格？
> 按照 run 中指定的复权方式计算，**持仓均价计算亦如此**。

### 2.2 pos.vwap 的真实含义

`pos.vwap` 是**持仓均价**（position average cost），不是市场 VWAP。

计算公式：

```
pos.vwap = Σ(每笔成交量 × 成交价) / Σ(成交量)
```

其中"成交价"是回测引擎模拟撮合的价格（后复权价）。

### 2.3 pos.market_value 的计算方式

```
pos.market_value = 持仓数量 × 当前后复权收盘价
```

由 gm SDK 内部自动计算。

### 2.4 回测中成交价的完整链路

```
run(backtest_adjust=ADJUST_POST)
    │
    ├── 1. 行情数据 → 后复权价
    │
    ├── 2. 下单 → 模拟撮合
    │       成交价 = 下一根 bar 的后复权开盘价
    │
    ├── 3. pos.vwap 计算
    │       vwap = Σ(成交量 × 后复权成交价) / Σ(成交量)
    │
    └── 4. pos.market_value 计算
            market_value = 持仓数量 × 当前后复权收盘价
```

---

## 3. 交易方向

### 3.1 PositionSide_Long 用于卖出的合理性

**结论**：合理，不需要改。

```python
order_target_volume(
    symbol=pos.symbol,
    volume=0,                        # 目标股数 = 0（清仓）
    position_side=PositionSide_Long, # 操作对象是多头仓位
    order_type=OrderType_Market
)
```

- `PositionSide_Long` = 多头方向
- `PositionSide_Short` = 空头方向
- A 股不允许做空，卖出时用 `PositionSide_Long` 表示"平掉多头仓位"

如果用 `PositionSide_Short`，SDK 会尝试开空仓，在 A 股回测中会报错。

---

## 参考资料

- [掘金量化帮助文档 - 回测问题](https://www.myquant.cn/docs2/faq/)
- [掘金量化帮助文档 - 基本函数](https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%9F%BA%E6%9C%AC%E5%87%BD%E6%95%B0.html)
