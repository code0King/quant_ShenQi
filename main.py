# coding=utf-8
"""
策略主入口

使用前请确保已创建 .env 文件，内容如下：
DONGCAI_TOKEN=your_actual_token_here
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from gm.api import *
from config import STRATEGY_CONFIG
from strategy import annual_rebalance, _backtest_logger, _finalize_last_record
from utils.backtest_logger import BacktestLogger

# 加载环境变量
load_dotenv()


def init(context):
    """策略初始化函数"""
    for k, v in STRATEGY_CONFIG.items():
        setattr(context, k, v)

    # 存储 context 引用供 finalize 使用
    import strategy
    strategy._context = context

    # 初始化回测日志（一次回测一个文件）
    strategy._backtest_logger = BacktestLogger()
    strategy._backtest_logger.log_params(
        backtest_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
        backtest_start=STRATEGY_CONFIG.get("backtest_start_time", ""),
        backtest_end=STRATEGY_CONFIG.get("backtest_end_time", ""),
        initial_cash=STRATEGY_CONFIG.get("backtest_initial_cash", 100000),
        commission_ratio=STRATEGY_CONFIG.get("commission_ratio", 0.0001),
        slippage_ratio=STRATEGY_CONFIG.get("slippage_ratio", 0.0001),
        rebalance_month=STRATEGY_CONFIG.get("rebalance_month"),
        top_n=STRATEGY_CONFIG.get("top_n"),
        filters=STRATEGY_CONFIG.get("filters"),
        cash_etf_symbol=STRATEGY_CONFIG.get("cash_etf_symbol"),
    )

    schedule(schedule_func=annual_rebalance, date_rule='1m', time_rule='09:35:00')


if __name__ == '__main__':
    token = os.getenv('DONGCAI_TOKEN', 'your_token_here')

    # 1. 设置SDK全局参数
    set_option(max_wait_time=600000)

    # 2. 启动回测任务
    run(
        strategy_id='39a728e5-659a-11f1-b503-f8893c26fc79',
        filename='main.py',
        mode=MODE_BACKTEST,
        token=token,

        # --- 回测时间范围（从配置读取）---
        backtest_start_time=STRATEGY_CONFIG["backtest_start_time"],
        backtest_end_time=STRATEGY_CONFIG["backtest_end_time"],

        # --- 资金与费率（从配置读取）---
        backtest_initial_cash=STRATEGY_CONFIG["backtest_initial_cash"],
        backtest_commission_ratio=STRATEGY_CONFIG["commission_ratio"],
        backtest_slippage_ratio=STRATEGY_CONFIG["slippage_ratio"],

        # --- 数据复权方式 ---
        backtest_adjust=ADJUST_POST,

        # --- 缓存检查 ---
        backtest_check_cache=1
    )

    # 3. 回测结束：填充最后一条调仓记录并保存日志
    import strategy
    if strategy._backtest_logger:
        # 最后一次调仓的实际持仓需要在此补录
        # (run() 返回后 context 不再可用，使用最后缓存的 context)
        try:
            _finalize_last_record(strategy._context)
        except Exception:
            pass
        strategy._backtest_logger.finalize(
            strategy._context.account().cash.balance +
            strategy._context.account().cash.market_value
        )

    print("\n\n" + "=" * 50)
    print("[DONE] [系统通知] 回测任务全部完成！")
    print("=" * 50)
