# tests/test_filters.py
"""过滤器逻辑测试（独立实现，不依赖 gm.api）"""
import pytest
import pandas as pd
import math
from datetime import datetime


def _apply_filters(data, filter_config, current_date_ts):
    """apply_filters 的独立副本，用于测试（避免导入依赖 gm.api 的 strategy 模块）"""
    for field, config in filter_config.items():
        val = data.get(field)
        if val is None:
            return False
        try:
            val = float(val)
            if math.isnan(val):
                return False
        except (TypeError, ValueError):
            return False

        if field == "listing_days":
            listed_date = data.get('listed_date')
            if not listed_date:
                return False
            if isinstance(listed_date, str):
                listed_date = pd.to_datetime(listed_date)
            if hasattr(listed_date, 'tz') and listed_date.tz is not None:
                listed_date = listed_date.tz_localize(None)
            days_diff = (current_date_ts - listed_date).days
            if config["min"] is not None and days_diff < config["min"]:
                return False
            if config["max"] is not None and days_diff > config["max"]:
                return False
            continue

        if config["min"] is not None and val < config["min"]:
            return False
        if config["max"] is not None and val > config["max"]:
            return False

    return True


def test_filter_passes():
    """正常通过所有筛选条件"""
    data = {"tot_mv": 5000000000, "pe_ttm_cut": 15, "roic": 20}
    config = {
        "tot_mv": {"min": 3000000000, "max": None},
        "pe_ttm_cut": {"min": 0, "max": 20},
        "roic": {"min": 15, "max": None},
    }
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is True


def test_filter_fails_min():
    """市值低于最小阈值"""
    data = {"tot_mv": 1000000000}
    config = {"tot_mv": {"min": 3000000000, "max": None}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is False


def test_filter_fails_max():
    """PE 高于最大阈值"""
    data = {"pe_ttm_cut": 25}
    config = {"pe_ttm_cut": {"min": 0, "max": 20}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is False


def test_filter_missing_value():
    """缺失字段返回 False"""
    data = {"tot_mv": 5000000000}
    config = {"pe_ttm_cut": {"min": 0, "max": 20}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is False


def test_filter_listing_days_pass():
    """上市天数达标"""
    data = {"listed_date": datetime(2020, 1, 1), "listing_days": 1000}
    config = {"listing_days": {"min": 365, "max": None}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is True


def test_filter_listing_days_fail():
    """上市天数不达标"""
    data = {"listed_date": datetime(2020, 1, 1), "listing_days": 1000}
    config = {"listing_days": {"min": 2000, "max": None}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is False


def test_filter_nan_value():
    """NaN 值返回 False"""
    data = {"pe_ttm_cut": float('nan')}
    config = {"pe_ttm_cut": {"min": 0, "max": 20}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is False


def test_filter_invalid_value():
    """非数值字符串返回 False"""
    data = {"pe_ttm_cut": "invalid"}
    config = {"pe_ttm_cut": {"min": 0, "max": 20}}
    assert _apply_filters(data, config, pd.Timestamp("2024-01-01")) is False