# tests/test_config.py
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import STRATEGY_CONFIG


def test_rebalance_month_range():
    """调仓月份必须在 1-12 之间"""
    month = STRATEGY_CONFIG["rebalance_month"]
    assert 1 <= month <= 12, f"调仓月份 {month} 超出范围 [1, 12]"


def test_top_n_positive():
    """选股数量必须为正整数"""
    assert STRATEGY_CONFIG["top_n"] > 0


def test_filters_have_source():
    """每个筛选条件必须指定 source"""
    for field, config in STRATEGY_CONFIG["filters"].items():
        assert "source" in config, f"筛选条件 {field} 缺少 source"


def test_data_fields_not_empty():
    """数据字段配置不能为空"""
    for category, fields in STRATEGY_CONFIG["data_fields"].items():
        assert len(fields) > 0, f"{category} 字段为空"