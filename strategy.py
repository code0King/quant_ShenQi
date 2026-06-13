# coding=utf-8
# ==========================================
# 📝 策略名称：灵活配置型多因子选股策略 (v2.1.0 超高效版)
# 功能描述：
# 1. 三阶段架构：数据获取 -> 数据分析 -> 交易执行
# 2. 全量批量获取：所有数据接口均支持全市场一次性获取
# 3. 智能流控：严格遵守各API的流控限制
#    - stk_get_daily_mktvalue_pt: 5min/100次, 24h/2万次
#    - stk_get_daily_valuation_pt: 5min/100次, 24h/2万次
#    - stk_get_finance_deriv_pt: 5min/60次, 24h/2万次
# 4. 数据缓存：自动保存/加载CSV，二次运行秒级完成
# 5. 统一配置：所有筛选指标自由组合
# ==========================================
"""策略核心逻辑模块"""

from gm.api import *
import pandas as pd
import numpy as np
import time
import os
import json
import math
from datetime import datetime
from config import STRATEGY_CONFIG, DATA_FULL_DIR, DATA_FILTERED_DIR, META_DIR, LOGS_DIR
from utils.backtest_logger import BacktestLogger


# ==========================================
# 全局流控
# ==========================================

class SmartRateLimiter:
    """简化版流控类（移除 threading.Lock，单线程无需锁）"""

    def __init__(self):
        self.general_requests = []
        self.GENERAL_SHORT_WINDOW = 300
        self.GENERAL_SHORT_LIMIT = 100

        self.finance_requests = []
        self.FINANCE_SHORT_WINDOW = 300
        self.FINANCE_SHORT_LIMIT = 60

        self.daily_count = 0
        self.DAILY_LIMIT = 20000
        self.last_reset_date = datetime.now().date()

    def _check_and_wait(self, request_list, window, limit, api_name):
        """检查并等待"""
        now = time.time()
        request_list[:] = [t for t in request_list if now - t < window]

        if len(request_list) >= limit:
            oldest = min(request_list)
            wait_time = window - (now - oldest) + 0.5
            if wait_time > 0:
                print(f"[WAIT] 触发{api_name}流控，等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                now = time.time()
                request_list[:] = [t for t in request_list if now - t < window]

    def wait_for_general_api(self):
        self._check_and_wait(self.general_requests, self.GENERAL_SHORT_WINDOW, self.GENERAL_SHORT_LIMIT, "通用API")
        self.general_requests.append(time.time())
        self._check_daily_limit()

    def wait_for_finance_api(self):
        self._check_and_wait(self.finance_requests, self.FINANCE_SHORT_WINDOW, self.FINANCE_SHORT_LIMIT, "财务API")
        self.finance_requests.append(time.time())
        self._check_daily_limit()

    def _check_daily_limit(self):
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_count = 0
            self.last_reset_date = current_date

        if self.daily_count >= self.DAILY_LIMIT:
            raise Exception("已达到每日2万次请求限制")

        self.daily_count += 1


api_limiter = SmartRateLimiter()


def ensure_directory(dir_path):
    """确保目录存在"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def get_data_filename(date_str, data_type="full"):
    """生成数据文件路径"""
    if data_type == "filtered":
        target_dir = DATA_FILTERED_DIR
    else:
        target_dir = DATA_FULL_DIR
    ensure_directory(target_dir)
    return os.path.join(target_dir, f"data_{date_str}_{data_type}.csv.gz")


def get_cache_filename(date_str):
    """生成缓存文件路径"""
    ensure_directory(META_DIR)
    return os.path.join(META_DIR, f"meta_{date_str}.json")


# ==========================================
# 数据管理层
# ==========================================

class DataManager:
    """数据管理器"""

    @staticmethod
    def save_full_data(date_str, data_list):
        """保存完整数据到本地"""
        if not data_list:
            return
        filename = get_data_filename(date_str, "full")
        try:
            df = pd.DataFrame(data_list)
            df.to_csv(filename, compression='gzip', index=False)
            print(f"[SAVE] [数据保存] 完整数据已保存至 {filename} (共{len(data_list)}条)")
        except Exception as e:
            print(f"[ERR] [数据保存失败] {e}")

    @staticmethod
    def load_full_data(date_str):
        """从本地加载完整数据"""
        filename = get_data_filename(date_str, "full")
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename, compression='gzip')
                # 缓存完整性校验：记录数少于1000条视为无效缓存（防止诊断模式采样数据污染）
                if len(df) < 1000:
                    print(f"[WARN] [缓存校验] {filename} 仅{len(df)}条记录，不足1000条，视为无效缓存，将重新获取")
                    return None
                data_list = df.to_dict('records')
                print(f"[SAVE] [数据加载] 已从 {filename} 加载完整数据 (共{len(data_list)}条)")
                return data_list
            except Exception as e:
                print(f"[WARN] [数据加载失败] {e}")
                return None
        return None

    @staticmethod
    def save_filtered_data(date_str, data_list):
        """保存筛选后的数据"""
        if not data_list:
            return
        filename = get_data_filename(date_str, "filtered")
        try:
            df = pd.DataFrame(data_list)
            df.to_csv(filename, compression='gzip', index=False)
            print(f"[SAVE] [筛选保存] 筛选数据已保存至 {filename} (共{len(data_list)}条)")
        except Exception as e:
            print(f"[ERR] [筛选保存失败] {e}")

    @staticmethod
    def load_filtered_data(date_str):
        """加载筛选后的数据"""
        filename = get_data_filename(date_str, "filtered")
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename, compression='gzip')
                data_list = df.to_dict('records')
                print(f"[SAVE] [筛选加载] 已从 {filename} 加载筛选数据")
                return data_list
            except Exception as e:
                print(f"[WARN] [筛选加载失败] {e}")
                return None
        return None

    @staticmethod
    def save_metadata(date_str, metadata):
        """保存元数据"""
        filename = get_cache_filename(date_str)
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] [元数据保存失败] {e}")

    @staticmethod
    def load_metadata(date_str):
        """加载元数据"""
        filename = get_cache_filename(date_str)
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] [元数据加载失败] {e}")
        return None


# ==========================================
# 数据获取模块
# ==========================================

def fetch_all_stock_data(context, current_date, start_date_query):
    """
    第一阶段：全量批量获取全部股票数据并保存到本地
    """
    print(f"\n[IN] === 第一阶段：数据获取 ({current_date}) ===")

    diagnostic_start_time = time.time() if context.DIAGNOSTIC_MODE else None
    if context.DIAGNOSTIC_MODE:
        print(f"\n[DIAG] [诊断模式] 已开启")
        print(f"   - 采样数量: {context.DIAGNOSTIC_SAMPLE_SIZE} 只股票")
        print(f"   - 跳过缓存: {context.DIAGNOSTIC_SKIP_CACHE}")

    cached_data = None
    if not context.DIAGNOSTIC_MODE or not context.DIAGNOSTIC_SKIP_CACHE:
        cached_data = DataManager.load_full_data(current_date)
        if cached_data is not None:
            print("[OK] 使用已存在的完整数据")
            return cached_data
    elif context.DIAGNOSTIC_MODE and context.DIAGNOSTIC_SKIP_CACHE:
        print("[FAST] [诊断模式] 跳过缓存，强制重新获取数据")

    print("[SEARCH] 获取股票池...")
    try:
        stock_list = get_symbols(
            sec_type1=1010,
            trade_date=current_date,
            skip_suspended=True,
            skip_st=True,
            df=True
        )
        if stock_list is None or stock_list.empty:
            print("[ERR] 未获取到股票列表")
            return []
    except Exception as e:
        print(f"[ERR] 获取股票列表失败: {e}")
        return []

    symbols_to_check = stock_list['symbol'].tolist()
    original_count = len(symbols_to_check)

    if context.DIAGNOSTIC_MODE:
        symbols_to_check = symbols_to_check[:context.DIAGNOSTIC_SAMPLE_SIZE]
        print(f"[DIAG] [诊断模式] 股票池已限制: {len(symbols_to_check)} 只 (原始: {original_count} 只)")
    else:
        print(f"[LIST] 股票池总数: {len(symbols_to_check)} 只")

    listed_date_map = {}
    if 'listed_date' in stock_list.columns:
        stock_list['listed_date'] = pd.to_datetime(stock_list['listed_date'])
        for _, row in stock_list.iterrows():
            listed_date_map[row['symbol']] = row['listed_date']

    data_fields_config = context.data_fields
    val_req = data_fields_config.get('valuation', [])
    deriv_req = data_fields_config.get('deriv', [])
    mktvalue_req = data_fields_config.get('mktvalue', ['tot_mv'])
    print(f"[TOOL] 数据获取配置: 市值类{mktvalue_req}, 估值类{val_req}, 财务类{deriv_req}")

    # ========== 步骤1：获取全市场市值数据 ==========
    step1_start = time.time()
    print("\n[DATA] 步骤1: 批量获取市值数据...")
    mv_map = {}
    try:
        api_limiter.wait_for_general_api()
        all_mv = stk_get_daily_mktvalue_pt(
            symbols=symbols_to_check,
            fields=','.join(mktvalue_req),
            trade_date=current_date,
            df=True
        )

        if all_mv is not None and not all_mv.empty:
            for _, row in all_mv.iterrows():
                symbol = row['symbol']
                mv_map[symbol] = {}
                for col in mktvalue_req:
                    if col in row.index:
                        mv_map[symbol][col] = row[col]
            step1_elapsed = time.time() - step1_start
            print(f"[OK] 获取到 {len(mv_map)} 只股票的市值数据 (耗时: {step1_elapsed:.2f}秒)")
        else:
            print("[WARN] 未获取到市值数据")
            return []
    except Exception as e:
        print(f"[ERR] 市值获取失败: {e}")
        return []

    # ========== 步骤2：获取全市场估值数据 ==========
    val_data_map = {}
    if val_req:
        step2_start = time.time()
        print(f"\n[UP] 步骤2: 批量获取估值数据 ({','.join(val_req)})...")
        try:
            api_limiter.wait_for_general_api()
            all_val = stk_get_daily_valuation_pt(
                symbols=symbols_to_check,
                fields=','.join(val_req),
                trade_date=current_date,
                df=True
            )

            if all_val is not None and not all_val.empty:
                for _, row in all_val.iterrows():
                    symbol = row['symbol']
                    val_data_map[symbol] = {}
                    for col in val_req:
                        if col in row.index:
                            val_data_map[symbol][col] = row[col]
                step2_elapsed = time.time() - step2_start
                print(f"[OK] 获取到 {len(val_data_map)} 只股票的估值数据 (耗时: {step2_elapsed:.2f}秒)")
            else:
                print("[WARN] 未获取到估值数据")
        except Exception as e:
            print(f"[ERR] 估值数据获取失败: {e}")

    # ========== 步骤3：获取全市场财务衍生数据 ==========
    deriv_data_map = {}
    if deriv_req:
        step3_start = time.time()
        print(f"\n[DOWN] 步骤3: 批量获取财务衍生数据 ({','.join(deriv_req)})...")
        try:
            api_limiter.wait_for_finance_api()

            all_deriv = stk_get_finance_deriv_pt(
                symbols=symbols_to_check,
                fields=','.join(deriv_req),
                rpt_type=12,          # 固定使用年报数据，避免不同调仓月份ROIC口径不一致
                data_type=101,        # 合并原始（未经修正的合并报表）
                date=current_date,
                df=True
            )

            if all_deriv is not None and not all_deriv.empty:
                print(f"   原始财务数据: {len(all_deriv)} 条记录")

                existing_fields = [f for f in deriv_req if f in all_deriv.columns]
                if existing_fields:
                    all_deriv = all_deriv.dropna(subset=existing_fields, how='all')
                    print(f"   剔除全空值后: {len(all_deriv)} 条记录")

                if not all_deriv.empty:
                    all_deriv['rpt_date'] = pd.to_datetime(all_deriv['rpt_date'])
                    all_deriv.sort_values(['symbol', 'rpt_date'], ascending=[True, False], inplace=True)
                    all_deriv.drop_duplicates(subset='symbol', keep='first', inplace=True)

                    for _, row in all_deriv.iterrows():
                        symbol = row['symbol']
                        deriv_data_map[symbol] = {}
                        for col in deriv_req:
                            if col in row.index:
                                deriv_data_map[symbol][col] = row[col]

                    step3_elapsed = time.time() - step3_start
                    print(f"[OK] 获取到 {len(deriv_data_map)} 只股票的财务数据（最新一期） (耗时: {step3_elapsed:.2f}秒)")
                else:
                    print("[WARN] 财务数据剔除空值后为空")
            else:
                print("[WARN] 未获取到财务数据")
        except Exception as e:
            print(f"[ERR] 财务数据获取失败: {e}")
            import traceback
            traceback.print_exc()

    # ========== 步骤4：合并所有数据 ==========
    step4_start = time.time()
    print("\n[LINK] 步骤4: 合并所有数据...")
    all_scanned_data = []

    current_date_ts = pd.Timestamp(current_date)

    for symbol in symbols_to_check:
        data = {'symbol': symbol}

        if symbol in mv_map:
            data.update(mv_map[symbol])

        if symbol in val_data_map:
            data.update(val_data_map[symbol])

        if symbol in deriv_data_map:
            data.update(deriv_data_map[symbol])

        if symbol in listed_date_map:
            listed_date = listed_date_map[symbol]
            data['listed_date'] = listed_date

            if isinstance(listed_date, str):
                listed_date = pd.to_datetime(listed_date)
            if hasattr(listed_date, 'tz') and listed_date.tz is not None:
                listed_date = listed_date.tz_convert('UTC').tz_localize(None)

            data['listing_days'] = (current_date_ts - listed_date).days

        if len(data) > 1:
            all_scanned_data.append(data)

    step4_elapsed = time.time() - step4_start
    print(f"[OK] 数据合并完成，共 {len(all_scanned_data)} 条有效记录 (耗时: {step4_elapsed:.2f}秒)")

    if context.DIAGNOSTIC_MODE:
        total_elapsed = time.time() - diagnostic_start_time
        print(f"\n[DIAG] [诊断模式 - 数据获取阶段完成]")
        print(f"   [OK] 股票池大小: {len(symbols_to_check)} 只")
        print(f"   [OK] 市值数据覆盖率: {len(mv_map)}/{len(symbols_to_check)} ({len(mv_map)/len(symbols_to_check)*100:.1f}%)")
        if val_req:
            print(f"   [OK] 估值数据覆盖率: {len(val_data_map)}/{len(symbols_to_check)} ({len(val_data_map)/len(symbols_to_check)*100:.1f}%)")
        if deriv_req:
            print(f"   [OK] 财务数据覆盖率: {len(deriv_data_map)}/{len(symbols_to_check)} ({len(deriv_data_map)/len(symbols_to_check)*100:.1f}%)")
        print(f"   [OK] 有效记录数: {len(all_scanned_data)} 条")
        print(f"   [TIME] 总耗时: {total_elapsed:.2f}秒")
        print(f"   [TIP] 提示: 这是诊断模式，仅用于验证流程正确性")

    DataManager.save_full_data(current_date, all_scanned_data)

    metadata = {
        "date": current_date,
        "total_stocks": len(symbols_to_check),
        "valid_records": len(all_scanned_data),
        "mv_count": len(mv_map),
        "val_count": len(val_data_map),
        "deriv_count": len(deriv_data_map),
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    DataManager.save_metadata(current_date, metadata)

    if context.DIAGNOSTIC_MODE:
        diagnostic_end_time = time.time()
        diagnostic_elapsed = diagnostic_end_time - diagnostic_start_time
        print(f"\n[DIAG] [诊断模式] 总耗时: {diagnostic_elapsed:.2f}秒")

    return all_scanned_data


# ==========================================
# 数据分析模块
# ==========================================

def apply_filters(data, filter_config, current_date_ts):
    """通用过滤器"""
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


def generate_diagnostic_report(all_data, filter_config):
    """生成诊断报告"""
    if not all_data:
        print("[WARN] 未获取到任何数据，无法生成诊断报告")
        return

    print(f"[SEARCH] 正在生成诊断报告 (样本数: {len(all_data)})...")
    df_all = pd.DataFrame(all_data)

    for field, config in filter_config.items():
        if field not in df_all.columns:
            print(f"   [WARN] 字段 [{field}] 缺失，跳过检查。")
            continue

        valid_data = df_all[field].dropna()
        if valid_data.empty:
            print(f"   [WARN] 字段 [{field}] 无有效数值。")
            continue

        min_val, max_val = valid_data.min(), valid_data.max()

        pass_count = 0
        for val in valid_data:
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            is_pass = True
            if config["min"] is not None and val < config["min"]:
                is_pass = False
            if config["max"] is not None and val > config["max"]:
                is_pass = False
            if is_pass:
                pass_count += 1

        pass_rate = (pass_count / len(valid_data)) * 100
        limit_str = f"[{config['min']}, {config['max']}]"
        print(f"   [DATA] {field:<15} | 范围: {limit_str:<20} | 实际分布: {min_val:.2f} ~ {max_val:.2f} | 达标: {pass_count} ({pass_rate:.1f}%)")


def analyze_and_filter_data(context, all_data, current_date):
    """
    第二阶段：对完整数据进行筛选和分析
    """
    print(f"\n[SEARCH] === 第二阶段：数据分析 ({current_date}) ===")

    filter_start_time = time.time() if context.DIAGNOSTIC_MODE else None

    cached_filtered = DataManager.load_filtered_data(current_date)
    if cached_filtered is not None:
        print("[OK] 使用已存在的筛选数据")
        return cached_filtered, False

    if not all_data:
        print("[WARN] 没有数据可供分析")
        return [], True

    current_date_ts = pd.Timestamp(current_date)
    qualified_stocks = [d for d in all_data if apply_filters(d, context.filters, current_date_ts)]

    filter_elapsed = time.time() - filter_start_time if filter_start_time else 0
    filter_rate = len(qualified_stocks) / len(all_data) * 100 if all_data else 0

    print(f"[UP] 筛选结果: {len(qualified_stocks)} 只股票符合条件 (总数: {len(all_data)})")

    if context.DIAGNOSTIC_MODE:
        print(f"\n[DIAG] [诊断模式 - 筛选阶段完成]")
        print(f"   [OK] 筛选率: {filter_rate:.2f}%")
        print(f"   [TIME] 筛选耗时: {filter_elapsed:.2f}秒")
        print(f"   [LIST] 筛选条件:")
        for field, config in context.filters.items():
            min_val = config.get('min', 'N/A')
            max_val = config.get('max', 'N/A')
            direction = config.get('direction', 'N/A')
            source = config.get('source', 'base')
            print(f"     - {field}: [{min_val}, {max_val}] ({direction}) [{source}]")

    if len(qualified_stocks) == 0:
        print(f"\n[ERR] [严重警告] 未选中任何股票！")
        print(f"[SEARCH] 正在生成详细诊断报告...")
        generate_diagnostic_report(all_data, context.filters)
        return [], True

    if len(qualified_stocks) < context.top_n:
        print(f"\n[WARN] [警告] 选中股票数量 ({len(qualified_stocks)}只) 不足目标数量 ({context.top_n}只)")
        print(f"[SEARCH] 正在生成诊断报告以分析原因...")
        generate_diagnostic_report(all_data, context.filters)
        print(f"[TIP] 将直接买入全部 {len(qualified_stocks)} 只符合条件的股票")
        DataManager.save_filtered_data(current_date, qualified_stocks)
        return qualified_stocks, False

    print(f"[OK] 股票数量充足 ({len(qualified_stocks)}只 >= {context.top_n}只)，将进行综合得分排序")

    DataManager.save_filtered_data(current_date, qualified_stocks)

    return qualified_stocks, False


def rank_and_select_stocks(context, qualified_stocks, is_empty=False):
    """
    对筛选后的股票进行排序和选择

    参数:
        context: 策略上下文
        qualified_stocks: 符合条件的股票列表
        is_empty: 是否没有任何股票符合条件
    
    返回:
        target_symbols: 最终选中的股票代码列表
    """
    if is_empty or not qualified_stocks:
        print(f"[ERR] 没有符合条件的股票，返回空列表")
        return []

    if len(qualified_stocks) <= context.top_n:
        print(f"\n[DATA] === 选股结果（数量不足）===")
        print(f"[OK] 股票数量不足，直接选中全部 {len(qualified_stocks)} 只股票")
        target_symbols = [d['symbol'] for d in qualified_stocks]

        if qualified_stocks:
            df_info = pd.DataFrame(qualified_stocks)
            scoring_fields = [k for k, v in context.filters.items() if v.get('direction') and k in df_info.columns]
            print_cols = ['symbol'] + scoring_fields + ['tot_mv']
            available_cols = [col for col in print_cols if col in df_info.columns]

            print(f"\n[LIST] 选中股票详情:")
            print(df_info[available_cols].to_string(index=False))
            print("=" * 50)

        return target_symbols

    print(f"\n[DATA] === 选股结果（综合排序）===")
    print(f"[DATA] 正在计算综合得分...")
    df_res = pd.DataFrame(qualified_stocks)

    scoring_fields = [k for k, v in context.filters.items() if v.get('direction') and k in df_res.columns]

    if not scoring_fields:
        print("[WARN] 没有配置排序指标，按市值从小到大排序")
        df_res['composite_score'] = df_res.get('tot_mv', 0)
        df_res.sort_values('composite_score', ascending=True, inplace=True)
    else:
        print(f"[TARGET] 排序指标: {', '.join(scoring_fields)}")
        total_score = 0
        for field in scoring_fields:
            direction = context.filters[field].get('direction', 'desc')
            is_ascending = (direction == 'asc')
            rank_series = df_res[field].rank(ascending=is_ascending, method='first', na_option='keep')
            rank_series = rank_series.fillna(999999)
            total_score += rank_series
            print(f"   - {field}: {'升序' if is_ascending else '降序'}")
        df_res['composite_score'] = total_score
        df_res.sort_values('composite_score', ascending=True, inplace=True)

    final_selection = df_res.head(context.top_n)
    target_symbols = final_selection['symbol'].tolist()

    print(f"\n[OK] 从 {len(qualified_stocks)} 只候选股票中选出前 {context.top_n} 只")
    print_cols = ['symbol'] + scoring_fields + ['tot_mv', 'composite_score']
    available_cols = [col for col in print_cols if col in final_selection.columns]

    print(f"\n[LIST] 最终选中股票详情（按综合得分排序）:")
    print(final_selection[available_cols].to_string(index=False))
    print("=" * 50)

    return target_symbols


# ==========================================
# 交易执行模块
# ==========================================

def execute_trades(context, target_symbols):
    """第三阶段：执行调仓交易"""
    print(f"\n[TRADE] === 第三阶段：交易执行 ===")

    try:
        target_weight = 1.0 / context.top_n if target_symbols else 0
        positions = context.account().positions()
        cash_symbol = context.cash_etf_symbol

        print("[DOWN] 执行调仓卖出...")
        for pos in positions:
            if pos.symbol == cash_symbol:
                continue
            if pos.symbol not in target_symbols:
                print(f"  卖出: {pos.symbol}")
                order_target_volume(
                    symbol=pos.symbol,
                    volume=0,
                    position_side=PositionSide_Long,
                    order_type=OrderType_Market
                )

        print("[UP] 执行股票买入...")
        for symbol in target_symbols:
            print(f"  买入/持有: {symbol} (权重: {target_weight:.2%})")
            order_target_percent(
                symbol=symbol,
                percent=target_weight,
                position_side=PositionSide_Long,
                order_type=OrderType_Market
            )

        if context.use_cash_management:
            actual_stock_weight = len(target_symbols) * target_weight
            cash_weight = 1.0 - actual_stock_weight
            if cash_weight > 0.01:
                print(f"[CASH] 现金管理: 买入 {cash_weight:.2%} 货币基金")
                order_target_percent(
                    symbol=cash_symbol,
                    percent=cash_weight,
                    position_side=PositionSide_Long,
                    order_type=OrderType_Market
                )
            else:
                print(f"[CASH] 清仓货币基金")
                order_target_volume(
                    symbol=cash_symbol,
                    volume=0,
                    position_side=PositionSide_Long,
                    order_type=OrderType_Market
                )
        print("[OK] 交易完毕。")
    except Exception as e:
        print(f"[ERR] 交易错误: {e}")


# ==========================================
# 模块级回测日志
# ==========================================

_backtest_logger = None          # BacktestLogger 实例
_selection_lookup = {}           # {symbol: {pe_ttm_cut, roic}} 当次选股数据
_context = None                  # 回测 context 引用（供 finalize 使用）


def _fill_previous_record(positions, equity, cash_symbol):
    """
    用实际持仓数据填充上一次调仓记录的 holdings

    在每次调仓开始时调用，此时 positions 是上一次调仓后的实际成交持仓
    buy_price 使用 pos.vwap（成交均价），amount = buy_price * volume
    """
    if not _backtest_logger or not _backtest_logger.data["rebalances"]:
        return

    prev = _backtest_logger.data["rebalances"][-1]
    actual_holdings = []
    for pos in positions:
        if pos.symbol == cash_symbol:
            continue
        info = _selection_lookup.get(pos.symbol, {})
        buy_price = round(getattr(pos, "vwap", 0), 2)
        volume = getattr(pos, "volume", 0)
        amount = round(buy_price * volume, 2)
        actual_holdings.append({
            "symbol": pos.symbol,
            "pe_ttm_cut": info.get("pe_ttm_cut"),
            "roic": info.get("roic"),
            "buy_price": buy_price,
            "volume": volume,
            "amount": amount,
        })

    prev["holdings"] = actual_holdings

    # 重新计算权重
    stock_mv = sum(h["amount"] for h in actual_holdings)
    cash_mv = equity - stock_mv if equity > stock_mv else 0
    prev["stock_weight"] = round(stock_mv / equity * 100, 2) if equity else 0
    prev["cash_weight"] = round(cash_mv / equity * 100, 2) if equity else 0


def _finalize_last_record(context):
    """
    回测结束时，用最终持仓填充最后一次调仓记录

    在 run() 返回后调用
    """
    if not _backtest_logger or not _backtest_logger.data["rebalances"]:
        return

    try:
        account = context.account()
        cash_obj = account.cash
        equity = cash_obj.balance + cash_obj.market_value
        positions = account.positions()
        cash_symbol = getattr(context, "cash_etf_symbol", "")
        _fill_previous_record(positions, equity, cash_symbol)
    except Exception as e:
        print(f"[WARN] 填充最终持仓失败: {e}")


# ==========================================
# 主策略流程
# ==========================================

def annual_rebalance(context):
    """
    年度调仓主函数
    在配置的调仓月份执行
    """
    global _selection_lookup

    rebalance_month = STRATEGY_CONFIG.get("rebalance_month", 1)
    if context.now.month != rebalance_month:
        return

    current_date = context.now.strftime('%Y-%m-%d')
    start_date_query = (context.now - pd.Timedelta(days=540)).strftime('%Y-%m-%d')

    print(f"\n{'=' * 60}")
    print(f"[TARGET] 策略执行日期: {current_date}")
    print(f"{'=' * 60}")

    total_start_time = time.time() if context.DIAGNOSTIC_MODE else None

    # --- 获取当前账户状态 ---
    account = context.account()
    cash_obj = account.cash
    equity = cash_obj.balance + cash_obj.market_value
    positions = account.positions()
    cash_symbol = context.cash_etf_symbol

    # --- 用实际持仓填充上一次调仓记录 ---
    if _backtest_logger and _backtest_logger.data["rebalances"]:
        _fill_previous_record(positions, equity, cash_symbol)
        print(f"[LOG] 上一次调仓记录已更新（实际持仓）")

    # --- 数据获取 & 选股 ---
    all_data = fetch_all_stock_data(context, current_date, start_date_query)

    if not all_data:
        print("[ERR] 数据获取失败，跳过本次调仓")
        execute_trades(context, [])
        return

    qualified_stocks, is_empty = analyze_and_filter_data(context, all_data, current_date)

    target_symbols = rank_and_select_stocks(context, qualified_stocks, is_empty)

    # --- 存储当次选股数据，供下次调仓填充使用 ---
    # 注意：不清空 _selection_lookup，保留历史数据供持续持仓的股票使用
    for d in qualified_stocks:
        sym = d.get('symbol')
        if sym in target_symbols:
            _selection_lookup[sym] = {
                'pe_ttm_cut': d.get('pe_ttm_cut'),
                'roic': d.get('roic'),
            }

    # --- 追加本次调仓记录（持仓将在下次调仓时填充实际数据） ---
    target_weight = 1.0 / context.top_n if target_symbols else 0
    stock_weight = len(target_symbols) * target_weight * 100
    cash_weight = 100 - stock_weight

    planned_holdings = [
        {
            "symbol": s,
            "pe_ttm_cut": _selection_lookup[s].get("pe_ttm_cut"),
            "roic": _selection_lookup[s].get("roic"),
            "buy_price": None,  # 待下次调仓时用实际 vwap 填充
            "volume": 0,
            "amount": 0,
        }
        for s in target_symbols
    ]

    if _backtest_logger:
        _backtest_logger.data["rebalances"].append({
            "date": current_date,
            "stock_count": len(target_symbols),
            "stock_weight": round(stock_weight, 2),
            "cash_weight": round(cash_weight, 2),
            "equity": round(equity, 2),
            "holdings": planned_holdings,
        })

    # --- 执行交易 ---
    execute_trades(context, target_symbols)

    if context.DIAGNOSTIC_MODE:
        total_elapsed = time.time() - total_start_time
        print(f"\n{'=' * 60}")
        print(f"[DIAG] [诊断模式 - 流程完成]")
        print(f"   [OK] 完整流程已成功执行")
        print(f"   [DATA] 选中股票数: {len(target_symbols)} 只")
        print(f"   [TIME] 总耗时: {total_elapsed:.2f}秒")
        print(f"   [TIP] 建议操作:")
        print(f"     1. 检查上述各阶段输出是否正常")
        print(f"     2. 确认筛选、排序逻辑符合预期")
        print(f"     3. 如无问题，设置 DIAGNOSTIC_MODE = False 进行正式回测")
        print(f"{'=' * 60}\n")
    else:
        print(f"\n{'=' * 60}")
        print(f"[OK] {current_date} 策略执行完成")
        print(f"{'=' * 60}\n")