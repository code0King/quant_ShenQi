# 灵活配置型多因子选股策略 - 重构设计文档

## 1. 项目背景

当前策略为单文件结构（`神奇公式-东财v0.8.6.txt`），代码量 700+ 行，存在以下问题：
- 单文件臃肿，职责混杂（配置、数据获取、分析、交易、流控全在一起）
- token 硬编码在代码中，存在安全风险
- 调仓月份硬编码为 1 月，不够灵活
- 缺乏回测日志记录功能
- 流控类引入 threading.Lock，在单线程回测引擎中反而增加开销

## 2. 设计目标

1. **模块化拆分**：将单文件拆分为 `config.py`、`strategy.py`、`main.py`
2. **敏感信息外置**：token 放入 `.env` 文件
3. **配置化调仓**：调仓月份可配置
4. **新增回测日志**：记录回测参数、收益统计、持仓明细
5. **流控简化**：移除不必要的 threading.Lock
6. **增加单元测试**：编写配置校验和过滤器逻辑的测试脚本

## 3. 目录结构

```
quant_ShenQi/
├── .env                          # 敏感配置：掘金 token（已加入 .gitignore）
├── .gitignore                    # Git 忽略规则
├── config.py                     # 策略配置（筛选条件、top_n、调仓月份等）
├── strategy.py                   # 策略核心逻辑（数据获取/分析/交易/流控）
├── main.py                       # 主入口：启动回测
├── utils/
│   ├── __init__.py
│   └── backtest_logger.py        # 回测日志记录器（参数、收益统计）
├── tests/
│   ├── __init__.py
│   ├── test_config.py            # 配置校验测试
│   ├── test_filters.py           # 过滤器逻辑测试
│   └── test_backtest_logger.py   # 日志模块测试
├── data/                         # 统一数据缓存目录
│   ├── full/                     # 完整数据缓存
│   ├── filtered/                 # 筛选后数据缓存
│   └── meta/                     # 元数据缓存
├── logs/                         # 回测日志输出目录
│   └── .gitkeep
├── .env.example                  # 环境变量模板
└── docs/
    └── superpowers/
        └── specs/
            └── 2025-01-15-project-refactor-design.md
```

## 4. 各模块职责

### 4.1 config.py（策略配置）
- `STRATEGY_CONFIG`：所有筛选条件、数据字段配置
- `REBALANCE_MONTH`：调仓月份（默认 1，可配置为 1-12）
- 路径配置：指向 `data/` 目录
- 其他参数：`top_n`、`use_cash_management`、`cash_etf_symbol` 等

### 4.2 strategy.py（策略核心）
- `DataManager`：数据缓存读写（CSV 格式，保留现有逻辑）
- `SmartRateLimiter`：API 流控（**简化**：移除 `threading.Lock`，改为简单 sleep）
- `fetch_all_stock_data()`：全量数据获取
- `analyze_and_filter_data()`：数据分析与筛选
- `rank_and_select_stocks()`：排序选股
- `execute_trades()`：交易执行
- `annual_rebalance()`：调仓主函数（使用 `config.REBALANCE_MONTH`）

### 4.3 utils/backtest_logger.py（新增）
回测结束后自动输出日志文件到 `logs/` 目录，记录：
- **回测参数**：策略名称、起止时间、初始资金、佣金率、滑点、调仓月份
- **收益统计**：总收益率、年化收益率、夏普比率、最大回撤、最终资产
- **持仓明细**：最终持仓股票及权重

### 4.4 main.py（主入口）
- 加载 `config` 和 `strategy`
- 从 `.env` 读取 `DONGCAI_TOKEN`
- 调用掘金 `run()` 启动回测

### 4.5 tests/（测试）
- `test_config.py`：验证配置项边界（如 `REBALANCE_MONTH` 在 1-12 之间）
- `test_filters.py`：测试 `apply_filters` 的各种场景
- `test_backtest_logger.py`：测试日志记录功能

## 5. 关键改进点

### 5.1 流控简化
- **原方案**：`threading.Lock` + 时间窗口统计
- **新方案**：简单 `time.sleep()` 控制调用间隔
- **原因**：掘金 SDK 为单线程回测引擎，不存在并发竞争，threading.Lock 反而增加开销

### 5.2 配置化调仓月份
- **原代码**：`if context.now.month != 1`
- **新代码**：`if context.now.month != config.REBALANCE_MONTH`
- 在 `config.py` 中增加 `REBALANCE_MONTH` 配置项

### 5.3 Token 外置
- 新增 `.env` 文件存放 `DONGCAI_TOKEN`
- 使用 `python-dotenv` 读取（掘金 SDK 环境）
- `.gitignore` 排除 `.env`，防止提交敏感信息

### 5.4 回测日志
- 新增 `backtest_logger.py` 模块
- 在 `annual_rebalance` 结束时调用，输出结构化日志
- 日志格式：JSON + 文本双格式，便于查看和后续分析

## 6. 实施计划

| 阶段 | 任务 | 说明 |
|------|------|------|
| **P1 基础设施** | 创建目录结构、`.gitignore`、`.env.example`、`config.py` | 先拆配置，风险最低 |
| **P2 核心迁移** | 将原单文件逻辑迁移到 `strategy.py` | 保持逻辑不变，仅结构调整 |
| **P3 新增功能** | `backtest_logger.py`、`tests/` 目录及测试脚本 | 日志 + 测试 |
| **P4 验证** | 本地运行确认无报错 | 确保回测流程完整 |
| **P5 文档编写** | 生成 README、CHANGELOG | 项目文档 |
| **P6 提交** | git commit | 版本记录 |

## 7. 兼容性说明

- 回测逻辑 100% 保留，仅做结构调整
- 数据缓存路径从 `strategy_data/`、`strategy_cache/` 改为 `data/full/`、`data/filtered/`、`data/meta/`
- 原有 `.csv.gz` 缓存文件可继续使用，只需移动到新目录

## 8. 待办事项

- [ ] 实现 `config.py`
- [ ] 实现 `strategy.py`（迁移原逻辑 + 流控简化）
- [ ] 实现 `main.py`
- [ ] 实现 `utils/backtest_logger.py`
- [ ] 编写 `tests/test_config.py`
- [ ] 编写 `tests/test_filters.py`
- [ ] 编写 `tests/test_backtest_logger.py`
- [ ] 验证回测流程
- [ ] 编写 README 和 CHANGELOG
