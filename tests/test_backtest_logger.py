# tests/test_backtest_logger.py
import pytest
import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.backtest_logger import BacktestLogger


class MockPosition:
    """模拟 gm.api 的 Position 对象"""
    def __init__(self, symbol, vwap, volume, market_value):
        self.symbol = symbol
        self.vwap = vwap
        self.volume = volume
        self.market_value = market_value
        self.pe_ttm_cut = None
        self.roic = None


def test_log_params():
    """记录回测参数"""
    logger = BacktestLogger()
    logger.log_params(initial_cash=100000, commission_ratio=0.0001)
    assert logger.data["params"]["initial_cash"] == 100000
    assert logger.data["params"]["commission_ratio"] == 0.0001


def test_append_rebalance():
    """追加调仓记录"""
    logger = BacktestLogger()
    logger.log_params(initial_cash=100000)

    positions = [
        MockPosition("SHSE.600519", 1800.0, 100, 190000.0),
        MockPosition("SZSE.000858", 150.0, 500, 80000.0),
        MockPosition("SHSE.511990", 100.0, 23000, 230000.0),  # 货币基金
    ]
    logger.append_rebalance("2006-06-01", positions, 500000.0,
                            stock_etf_symbol="SHSE.511990")

    assert len(logger.data["rebalances"]) == 1
    rec = logger.data["rebalances"][0]
    assert rec["date"] == "2006-06-01"
    assert rec["stock_count"] == 2
    assert rec["equity"] == 500000.0
    # 股票权重 = (190000 + 80000) / 500000 * 100 = 54%
    assert rec["stock_weight"] == 54.0
    # 现金权重 = 230000 / 500000 * 100 = 46%
    assert rec["cash_weight"] == 46.0
    # 持仓明细
    assert len(rec["holdings"]) == 2
    assert rec["holdings"][0]["symbol"] == "SHSE.600519"
    assert rec["holdings"][0]["buy_price"] == 1800.0
    assert rec["holdings"][0]["volume"] == 100
    # amount = buy_price * volume = 1800.0 * 100 = 180000.0
    assert rec["holdings"][0]["amount"] == 180000.0


def test_append_multiple_rebalances():
    """多次调仓追加记录"""
    logger = BacktestLogger()
    logger.log_params(initial_cash=100000)

    pos1 = [MockPosition("SHSE.600000", 10.0, 1000, 11000.0)]
    logger.append_rebalance("2006-06-01", pos1, 100000.0)

    pos2 = [MockPosition("SHSE.600036", 15.0, 800, 13000.0)]
    logger.append_rebalance("2007-06-01", pos2, 110000.0)

    assert len(logger.data["rebalances"]) == 2
    assert logger._equity_list == [("2006-06-01", 100000.0),
                                    ("2007-06-01", 110000.0)]


def test_finalize_computes_returns(tmp_path, monkeypatch):
    """finalize 计算收益指标"""
    monkeypatch.setattr("utils.backtest_logger.LOGS_DIR", str(tmp_path))

    logger = BacktestLogger()
    logger.log_params(initial_cash=100000)

    pos = [MockPosition("SHSE.600000", 10.0, 1000, 110000.0)]
    logger.append_rebalance("2024-06-01", pos, 110000.0)
    logger.append_rebalance("2025-06-01", pos, 120000.0)

    filename = logger.finalize(120000.0)

    assert os.path.exists(filename)
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ret = data["returns"]
    assert ret["initial_cash"] == 100000
    assert ret["final_equity"] == 120000
    assert ret["total_return"] == pytest.approx(0.2, abs=1e-4)
    assert ret["annual_return"] is not None
    assert ret["max_drawdown"] is not None


def test_save_creates_file(tmp_path, monkeypatch):
    """保存日志文件"""
    monkeypatch.setattr("utils.backtest_logger.LOGS_DIR", str(tmp_path))

    logger = BacktestLogger()
    logger.log_params(initial_cash=100000)
    filename = logger.finalize(100000.0)

    assert os.path.exists(filename)
    assert filename.startswith(str(tmp_path))
    assert filename.endswith(".json")
