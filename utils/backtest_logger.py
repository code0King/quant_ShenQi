# utils/backtest_logger.py
# coding=utf-8
"""回测日志记录器 — 一次回测生成一个 JSON 文件"""

import json
import math
import os
from datetime import datetime
from config import LOGS_DIR


class BacktestLogger:
    """
    回测日志记录器

    生命周期:
      1. init() 时创建，存入 context.backtest_logger
      2. 每次调仓调用 append_rebalance() 追加记录
      3. 回测结束后调用 finalize() 计算收益并保存
    """

    def __init__(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        self.data = {
            "strategy_name": "灵活配置型多因子选股策略",
            "params": {},
            "returns": {},
            "rebalances": [],
        }
        self._initial_cash = 0
        self._equity_list = []          # [(date_str, equity), ...]

    # --------------------------------------------------
    # 参数记录
    # --------------------------------------------------
    def log_params(self, **kwargs):
        """记录回测参数（只需调用一次）"""
        self.data["params"].update(kwargs)
        self._initial_cash = kwargs.get("initial_cash", 0)

    # --------------------------------------------------
    # 调仓记录
    # --------------------------------------------------
    def append_rebalance(self, date, positions, equity,
                         stock_etf_symbol=None):
        """
        追加一次调仓记录

        参数:
            date: 调仓日期字符串, 如 "2006-06-01"
            positions: context.account().positions() 返回的持仓列表
            equity: context.account().equity() 总权益
            stock_etf_symbol: 货币基金 symbol，用于区分现金仓位
        """
        if stock_etf_symbol is None:
            from config import STRATEGY_CONFIG
            stock_etf_symbol = STRATEGY_CONFIG.get("cash_etf_symbol", "")

        stock_weight = 0.0
        cash_weight = 0.0
        holdings = []

        for pos in positions:
            mv = getattr(pos, "market_value", 0) or 0
            weight = (mv / equity * 100) if equity else 0

            if pos.symbol == stock_etf_symbol:
                cash_weight += weight
            else:
                stock_weight += weight
                buy_price = round(getattr(pos, "vwap", 0), 2)
                volume = getattr(pos, "volume", 0)
                amount = round(buy_price * volume, 2)
                holdings.append({
                    "symbol": pos.symbol,
                    "pe_ttm_cut": getattr(pos, "pe_ttm_cut", None),
                    "roic": getattr(pos, "roic", None),
                    "buy_price": buy_price,
                    "volume": volume,
                    "amount": amount,
                })

        self.data["rebalances"].append({
            "date": date,
            "stock_count": len(holdings),
            "stock_weight": round(stock_weight, 2),
            "cash_weight": round(cash_weight, 2),
            "equity": round(equity, 2),
            "holdings": holdings,
        })

        self._equity_list.append((date, equity))

    # --------------------------------------------------
    # 收益计算 & 保存
    # --------------------------------------------------
    def finalize(self, final_equity):
        """
        回测结束后调用：计算收益指标并保存 JSON

        参数:
            final_equity: 回测结束时的总权益 context.account().equity()
        """
        self._compute_returns(final_equity)
        return self._save()

    def _compute_returns(self, final_equity):
        """计算收益统计指标"""
        initial = self._initial_cash
        if initial <= 0:
            self.data["returns"] = {}
            return

        total_return = (final_equity - initial) / initial

        # 年化收益：从权益序列首尾日期计算
        annual_return = None
        if len(self._equity_list) >= 2:
            first_date = self._equity_list[0][0]
            last_date = self._equity_list[-1][0]
            try:
                d1 = datetime.strptime(first_date, "%Y-%m-%d")
                d2 = datetime.strptime(last_date, "%Y-%m-%d")
                years = (d2 - d1).days / 365.25
                if years > 0:
                    annual_return = (1 + total_return) ** (1 / years) - 1
            except (ValueError, ZeroDivisionError):
                pass

        # 夏普比率 & 最大回撤：基于调仓频率的权益序列
        sharpe = None
        max_drawdown = None
        if len(self._equity_list) >= 2:
            equities = [e for _, e in self._equity_list]
            # 简化年化：假设每年调仓一次，收益率 = 权益变化率
            returns = []
            for i in range(1, len(equities)):
                if equities[i - 1] > 0:
                    returns.append((equities[i] - equities[i - 1]) / equities[i - 1])

            if returns:
                avg_r = sum(returns) / len(returns)
                var_r = sum((r - avg_r) ** 2 for r in returns) / len(returns)
                std_r = math.sqrt(var_r) if var_r > 0 else 0
                # 年化：假设每年调仓一次，无风险利率按 2.5% 估算
                risk_free_annual = 0.025
                risk_free_per_period = risk_free_annual  # 每年一次
                if std_r > 0:
                    sharpe = (avg_r - risk_free_per_period) / std_r

                # 最大回撤
                peak = equities[0]
                max_dd = 0
                for eq in equities:
                    if eq > peak:
                        peak = eq
                    dd = (peak - eq) / peak if peak > 0 else 0
                    if dd > max_dd:
                        max_dd = dd
                max_drawdown = -max_dd

        self.data["returns"] = {
            "initial_cash": round(initial, 2),
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 6),
            "annual_return": round(annual_return, 6) if annual_return is not None else None,
            "sharpe": round(sharpe, 4) if sharpe is not None else None,
            "max_drawdown": round(max_drawdown, 6) if max_drawdown is not None else None,
        }

    def _save(self):
        """保存日志到 JSON 文件（一次回测一个文件）"""
        run_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(LOGS_DIR, f"backtest_{run_time}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"[DATA] 回测日志已保存至 {filename}")
        return filename
