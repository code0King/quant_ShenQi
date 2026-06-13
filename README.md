# 神奇公式量化策略 (东财版)

基于乔尔·格林布拉特(Joel Greenblatt)的神奇公式策略，适配东方财富数据接口的量化实现。

## 功能特性
- 模块化架构：`config.py` + `strategy.py` + `main.py`
- 可配置调仓月份（`STRATEGY_CONFIG["rebalance_month"]`）
- 结构化数据缓存目录：`data/full/`, `data/filtered/`, `data/meta/`
- 详细的回测日志（`utils/backtest_logger.py`）

## 快速开始
1. 安装依赖：
```bash
pip install -r requirements.txt
```
2. 配置`.env`文件：
```ini
DONGCAI_TOKEN=您的东方财富Token
```
3. 运行策略：
```bash
python main.py
```

## 目录结构
```
quant_ShenQi/
├── config.py        # 策略配置
├── strategy.py      # 核心策略逻辑
├── main.py          # 主入口
├── data/            # 缓存数据
│   ├── full/        # 完整数据集
│   ├── filtered/    # 过滤后数据
│   └── meta/        # 元数据
├── logs/            # 回测日志（每次回测一个 JSON）
├── utils/
│   └── backtest_logger.py  # 回测日志记录器
├── tests/           # 单元测试
└── docs/
    └── technical_notes.md  # 技术笔记
```

## 模块职责

| 模块 | 职责 |
|------|------|
| `config.py` | 策略配置（筛选条件、调仓参数、资金费率等） |
| `strategy.py` | 核心逻辑（数据获取、筛选排序、交易执行、日志记录） |
| `main.py` | 入口函数（初始化、定时任务、回测启动） |
| `utils/backtest_logger.py` | 回测日志记录器（参数、调仓记录、收益计算） |

## 数据流

```
数据获取（fetch_all_stock_data）
    ↓
数据筛选（analyze_and_filter_data）
    ↓
排序选股（rank_and_select_stocks）
    ↓
交易执行（execute_trades）
    ↓
日志记录（BacktestLogger）
```

## 回测日志

每次回测生成一个 JSON 文件，保存在 `logs/` 目录。

### 日志结构

```json
{
  "strategy_name": "策略名称",
  "params": {
    "backtest_time": "回测执行时间",
    "backtest_start": "回测开始时间",
    "backtest_end": "回测结束时间",
    "initial_cash": 100000,
    "rebalance_month": 6,
    "top_n": 20,
    "filters": {}
  },
  "returns": {
    "initial_cash": 100000,
    "final_equity": 182595.35,
    "total_return": 0.825954,
    "annual_return": null,
    "sharpe": null,
    "max_drawdown": null
  },
  "rebalances": [
    {
      "date": "2005-06-01",
      "stock_count": 7,
      "stock_weight": 29.18,
      "cash_weight": 70.82,
      "equity": 100000.0,
      "holdings": [
        {
          "symbol": "SHSE.600002",
          "pe_ttm_cut": 6.9787,
          "roic": 8.1426739,
          "buy_price": 6.49,
          "volume": 700,
          "amount": 4543.0
        }
      ]
    }
  ]
}
```

### holdings 字段说明

| 字段 | 说明 |
|------|------|
| `symbol` | 股票代码 |
| `pe_ttm_cut` | 扣除非经常性损益的市盈率(TTM) |
| `roic` | 投入资本回报率 |
| `buy_price` | 买入均价（`pos.vwap`，后复权成交均价） |
| `volume` | 持仓数量（股） |
| `amount` | 买入金额（`buy_price × volume`） |

## 测试
```bash
pytest tests/
```

## 技术笔记

交易机制、价格复权等技术细节，参见 `docs/technical_notes.md`。
