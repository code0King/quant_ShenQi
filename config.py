# coding=utf-8
"""策略配置模块"""

import os

# ==========================================
# 路径配置
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FULL_DIR = os.path.join(DATA_DIR, "full")
DATA_FILTERED_DIR = os.path.join(DATA_DIR, "filtered")
META_DIR = os.path.join(DATA_DIR, "meta")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# 确保目录存在
for _dir in [DATA_DIR, DATA_FULL_DIR, DATA_FILTERED_DIR, META_DIR, LOGS_DIR]:
    os.makedirs(_dir, exist_ok=True)

# ==========================================
# 策略配置
# ==========================================
STRATEGY_CONFIG = {
    # --- 统一筛选指标 (自由组合) ---
    "filters": {
        # 基础过滤条件
        # "listing_days": {"min": 365, "max": None, "source": "base"},
        # "listing_days": {"min": 1095, "max": None, "source": "base"},
        "tot_mv": {"min": 3000000000, "max": None, "source": "base"},

        # 估值因子
        # "pe_ttm": {"min": 0, "max": 15, "source": "valuation", "direction": "asc"},
        "pe_ttm_cut": {"min": 0, "max": 20, "source": "valuation", "direction": "asc"},

        # 财务因子
        # "roa": {"min": 15, "max": None, "source": "deriv", "direction": "desc"},
        # "roe": {"min": 10, "max": None, "source": "deriv", "direction": "desc"},
        # "roe_cut": {"min": 15, "max": None, "source": "deriv", "direction": "desc"},
        # "ast_liab_rate": {"min": 0, "max": 50, "source": "deriv", "direction": "asc"},
        "roic": {"min": 15, "max": None, "source": "deriv", "direction": "desc"},
    },

    # --- 独立的数据获取配置 ---
    "data_fields": {
        # 市值数据字段
        # - tot_mv: 总市值，单位元
        # - a_mv: A股流通市值(含限售股)，单位元
        # - ev_ebitda: EV/EBITDA，单位倍
        "mktvalue": ["tot_mv", "a_mv", "ev_ebitda"],

        # 估值数据字段
        # - pe_ttm: 市盈率(TTM)，单位倍
        # - pe_ttm_cut: 市盈率(TTM) 扣除非经常性损益，单位倍
        # - pb_mrq: 市净率(最新报告期MRQ)，单位倍
        # - pcf_ttm_oper: 市现率(经营现金流,TTM)，单位倍
        # - ps_ttm: 市销率(TTM)，单位倍
        # - dy_ttm: 股息率(TTM)，单位%
        # - dy_lfy: 股息率(上一财年LFY)，单位%
        "valuation": ["pe_ttm", "pe_ttm_cut", "pb_mrq", "pcf_ttm_oper", "ps_ttm", "dy_ttm", "dy_lfy"],

        # 财务衍生数据字段
        # - roe: 净资产收益率ROE(摊薄)，单位%
        # - roe_cut: 净资产收益率ROE(扣除/摊薄)，单位%
        # - roa: 总资产报酬率ROA，单位%
        # - roic: 投入资本回报率ROIC，单位%
        # - sale_gpm: 销售毛利率(GPM)，单位%
        # - sale_npm: 销售净利率(NPM)，单位%
        # - ast_liab_rate: 资产负债率，单位%
        # - int_debt_tic: 带息负债/全部投入资本，单位%
        # - ocf_toi: 经营性现金净流量/营业总收入
        # - net_prof_cut_np: 扣除非经常性损益的净利润/净利润，单位%
        # - tg_ast_ta: 有形资产/总资产，单位%
        # - fcff: 企业自由现金流量FCFF，单位元
        # - fcfe: 股权自由现金流量FCFE，单位元
        "deriv": ["roe", "roe_cut", "roa", "roic", "sale_gpm", "sale_npm", "ast_liab_rate", "int_debt_tic",
                  "ocf_toi", "net_prof_cut_np", "tg_ast_ta", "fcff", "fcfe"],
    },

    # --- 排序与选股参数 ---
    "top_n": 20,

    # --- 调仓配置 ---
    "rebalance_month": 6,  # 调仓月份，1-12

    # --- 回测时间范围 (run() 使用) ---
    "backtest_start_time": "2005-01-01 09:00:00",
    "backtest_end_time": "2025-12-31 15:00:00",

    # --- 资金与费率设置 ---
    "backtest_initial_cash": 100000,     # 初始资金：10万
    "commission_ratio": 0.0001,          # 佣金费率：万分之一
    "slippage_ratio": 0.0001,           # 滑点比率：万分之一

    # --- 闲置资金管理配置 ---
    "use_cash_management": True,
    "cash_etf_symbol": "SHSE.511990",

    # --- 运行参数配置 ---
    "DIAGNOSTIC_MODE": False,           # 是否开启诊断模式
    "DIAGNOSTIC_SAMPLE_SIZE": 50,       # 诊断模式下的采样股票数量
    "DIAGNOSTIC_SKIP_CACHE": True,      # 诊断模式下是否跳过缓存（强制重新获取）

    # --- 数据管理配置 ---
    "DATA_FULL_DIR": DATA_FULL_DIR,
    "DATA_FILTERED_DIR": DATA_FILTERED_DIR,
    "CACHE_DIR": META_DIR,
}