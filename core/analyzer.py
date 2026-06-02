import re
from pathlib import Path

import pandas as pd

from core.models import AnalysisResult


REQUIRED_COLUMNS = [
    "经销商名称",
    "单据日期",
    "营销分类",
    "商品名称",
    "单位",
    "已发数量",
    "单价",
    "金额",
    "尺寸",
]

HEATER_CATEGORY_CODES = {"A", "X", "Z", "T", "S", "J", "G", "D+", "C"}
APPLIANCE_EXTRA_CATEGORIES = {"凉霸"}
HONEYCOMB_CATEGORIES = {"7mm大板", "9mm大板"}
SIZE_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*\*\s*(\d+(?:\.\d+)?)\s*$")
MODEL_SPLIT_PATTERN = re.compile(r"[（(]")
PRODUCT_REMARK_SPLIT_PATTERN = re.compile(r"[（(]")
SERIES_SUFFIX = "系列"


class AnalysisError(Exception):
    """用于向界面展示的友好分析错误。"""


def _money_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _text_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _normalize_category(value: object) -> str:
    """统一营销分类中的常见录入差异，避免取暖器分类漏判。"""
    text = "" if pd.isna(value) else str(value).strip()
    return text.replace("＋", "+").replace(" ", "").replace("\u3000", "")


def _is_heater_category(value: object) -> bool:
    """取暖器/电器分类识别，兼容 A 与 A系列 等录入方式。"""
    category = _normalize_category(value)
    if category in APPLIANCE_EXTRA_CATEGORIES:
        return True
    if category in HEATER_CATEGORY_CODES:
        return True
    if category.endswith(SERIES_SUFFIX):
        return category.removesuffix(SERIES_SUFFIX) in HEATER_CATEGORY_CODES
    return False


def _parse_area(size: object, quantity: float) -> float:
    """尺寸格式为 数字*数字 时，按毫米面积换算平方米。"""
    match = SIZE_PATTERN.match("" if pd.isna(size) else str(size))
    if not match:
        return 0.0

    length = float(match.group(1))
    width = float(match.group(2))
    return length * width / 1_000_000 * quantity


def _heater_model_name(product_name: object) -> str:
    """取暖器按括号前的型号归并，例如 DB100-FH-JS2（白）归为 DB100-FH-JS2。"""
    text = "" if pd.isna(product_name) else str(product_name).strip()
    model = MODEL_SPLIT_PATTERN.split(text, maxsplit=1)[0].strip()
    if re.search(r"DB\d+-F[HS]-JS2$", model, flags=re.IGNORECASE):
        return "JS2"
    return model


def _product_rank_name(product_name: object) -> str:
    """商品金额排行时忽略括号内工艺/颜色备注。"""
    text = "" if pd.isna(product_name) else str(product_name).strip()
    return PRODUCT_REMARK_SPLIT_PATTERN.split(text, maxsplit=1)[0].strip()


def read_excel_file(file_path: str | Path) -> pd.DataFrame:
    try:
        return pd.read_excel(file_path, engine="openpyxl")
    except Exception as exc:
        raise AnalysisError(f"Excel 读取失败，请确认文件未损坏且格式为 .xlsx/.xlsm。\n\n错误信息：{exc}") from exc


def analyze_excel(file_path: str | Path, cost_path: str | Path | None = None) -> AnalysisResult:
    raw_df = read_excel_file(file_path)
    if raw_df.empty:
        raise AnalysisError("Excel 中没有可分析的数据。")
    source_row_count = len(raw_df)

    missing = [col for col in REQUIRED_COLUMNS if col not in raw_df.columns]
    if missing:
        raise AnalysisError("Excel 缺少必要字段：\n" + "、".join(missing))

    df = raw_df[REQUIRED_COLUMNS].copy()
    df["经销商名称"] = _text_series(df["经销商名称"])
    df["营销分类"] = _text_series(df["营销分类"])
    df["商品名称"] = _text_series(df["商品名称"])
    df["单位"] = _text_series(df["单位"])
    df["尺寸"] = _text_series(df["尺寸"])
    df["已发数量"] = _money_series(df["已发数量"])
    df["单价"] = _money_series(df["单价"])
    df["金额"] = _money_series(df["金额"])
    df["单据日期"] = pd.to_datetime(df["单据日期"], errors="coerce")
    df["营销分类_匹配"] = df["营销分类"].apply(_normalize_category)

    df = df[df["商品名称"] != ""].copy()
    if df.empty:
        raise AnalysisError("没有找到有效的商品数据，请检查“商品名称”列。")

    ignored_mask = (
        (df["营销分类_匹配"] == "7mm大板")
        & df["商品名称"].str.contains("标准板|标准版", case=False, regex=True, na=False)
    )
    ignored_detail = df[ignored_mask].copy().reset_index(drop=True)
    df = df[~ignored_mask].copy()
    if df.empty:
        raise AnalysisError("剔除 7mm 大板标准板/标准版后，没有可分析的数据。")

    df["日期"] = df["单据日期"].dt.date
    df["周"] = df["单据日期"].dt.to_period("W").astype(str)
    df["月份"] = df["单据日期"].dt.to_period("M").astype(str)
    df["年份"] = df["单据日期"].dt.year
    df["月份序号"] = df["单据日期"].dt.month
    df["是否取暖器"] = df["营销分类"].apply(_is_heater_category)
    df["是否蜂窝板"] = df["营销分类_匹配"].isin(HONEYCOMB_CATEGORIES)
    df["面积㎡"] = [
        _parse_area(size, qty) if is_honeycomb else 0.0
        for size, qty, is_honeycomb in zip(df["尺寸"], df["已发数量"], df["是否蜂窝板"])
    ]

    dealer_values = [name for name in df["经销商名称"].unique().tolist() if name]
    dealer_name = dealer_values[0] if dealer_values else "未填写"
    valid_dates = df["单据日期"].dropna()
    period_start = valid_dates.min() if not valid_dates.empty else None
    period_end = valid_dates.max() if not valid_dates.empty else None

    product_summary = (
        df.groupby("商品名称", as_index=False)
        .agg(已发数量=("已发数量", "sum"), 金额=("金额", "sum"))
        .sort_values("金额", ascending=False)
    )
    product_amount_df = df.copy()
    product_amount_df["排行商品名称"] = product_amount_df["商品名称"].apply(_product_rank_name)
    product_amount_summary = (
        product_amount_df[product_amount_df["排行商品名称"] != ""]
        .groupby("排行商品名称", as_index=False)
        .agg(已发数量=("已发数量", "sum"), 金额=("金额", "sum"))
        .rename(columns={"排行商品名称": "商品名称"})
        .sort_values("金额", ascending=False)
    )

    category_summary = (
        df.groupby("营销分类", as_index=False)
        .agg(已发数量=("已发数量", "sum"), 金额=("金额", "sum"))
        .sort_values("金额", ascending=False)
    )

    heater_df = df[df["是否取暖器"]].copy()
    heater_df["型号"] = heater_df["商品名称"].apply(_heater_model_name)
    heater_top3 = (
        heater_df[heater_df["型号"] != ""]
        .groupby("型号", as_index=False)
        .agg(已发数量=("已发数量", "sum"), 金额=("金额", "sum"))
        .sort_values("已发数量", ascending=False)
        .head(3)
    )

    honeycomb_df = df[df["是否蜂窝板"]].copy()
    honeycomb_summary = (
        honeycomb_df.groupby("商品名称", as_index=False)
        .agg(**{"面积㎡": ("面积㎡", "sum"), "金额": ("金额", "sum")})
        .sort_values("面积㎡", ascending=False)
        if not honeycomb_df.empty
        else pd.DataFrame(columns=["商品名称", "面积㎡", "金额"])
    )

    honeycomb_size_summary = (
        honeycomb_df[honeycomb_df["面积㎡"] > 0]
        .groupby("尺寸", as_index=False)
        .agg(**{"面积㎡": ("面积㎡", "sum"), "金额": ("金额", "sum")})
        .sort_values("面积㎡", ascending=False)
        if not honeycomb_df.empty
        else pd.DataFrame(columns=["尺寸", "面积㎡", "金额"])
    )

    monthly_trend = (
        df.dropna(subset=["单据日期"])
        .groupby(["年份", "月份序号"], as_index=False)
        .agg(金额=("金额", "sum"))
        .sort_values(["年份", "月份序号"])
    )

    category_margin_summary = pd.DataFrame(columns=["营销分类", "销售金额", "成本金额", "毛利额", "毛利率"])
    missing_cost_summary = pd.DataFrame(columns=["状态", "营销分类", "商品名称", "行数", "已发数量", "金额"])
    cost_exception_summary = pd.DataFrame(columns=["状态", "营销分类", "商品名称", "行数", "已发数量", "金额"])
    gross_amount = 0.0
    gross_profit = 0.0
    gross_margin_rate = 0.0
    missing_cost_amount = 0.0
    missing_cost_row_count = 0
    cost_exception_amount = 0.0
    cost_exception_row_count = 0

    if cost_path:
        from core.costing import apply_costing

        df, cost_stats = apply_costing(df, cost_path)
        category_margin_summary = cost_stats["category_margin_summary"]
        missing_cost_summary = cost_stats["missing_cost_summary"]
        cost_exception_summary = cost_stats["cost_exception_summary"]
        gross_amount = float(cost_stats["gross_amount"])
        gross_profit = float(cost_stats["gross_profit"])
        gross_margin_rate = float(cost_stats["gross_margin_rate"])
        missing_cost_amount = float(cost_stats["missing_cost_amount"])
        missing_cost_row_count = int(cost_stats["missing_cost_row_count"])
        cost_exception_amount = float(cost_stats["cost_exception_amount"])
        cost_exception_row_count = int(cost_stats["cost_exception_row_count"])

    return AnalysisResult(
        dealer_name=dealer_name,
        clean_detail=df.sort_values("单据日期", na_position="last").reset_index(drop=True),
        product_summary=product_summary.reset_index(drop=True),
        product_amount_summary=product_amount_summary.reset_index(drop=True),
        category_summary=category_summary.reset_index(drop=True),
        heater_top3=heater_top3.reset_index(drop=True),
        top3_products_by_amount=product_amount_summary.head(3).reset_index(drop=True),
        honeycomb_summary=honeycomb_summary.reset_index(drop=True),
        honeycomb_size_summary=honeycomb_size_summary.reset_index(drop=True),
        monthly_trend=monthly_trend.reset_index(drop=True),
        total_amount=float(df["金额"].sum()),
        total_honeycomb_area=float(df["面积㎡"].sum()),
        period_start=period_start,
        period_end=period_end,
        source_row_count=source_row_count,
        ignored_detail=ignored_detail,
        category_margin_summary=category_margin_summary,
        missing_cost_summary=missing_cost_summary,
        cost_exception_summary=cost_exception_summary,
        gross_amount=gross_amount,
        gross_profit=gross_profit,
        gross_margin_rate=gross_margin_rate,
        missing_cost_amount=missing_cost_amount,
        missing_cost_row_count=missing_cost_row_count,
        cost_exception_amount=cost_exception_amount,
        cost_exception_row_count=cost_exception_row_count,
    )
