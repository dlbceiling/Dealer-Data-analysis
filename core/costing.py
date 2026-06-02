import re
from pathlib import Path

import pandas as pd

from core.analyzer import AnalysisError, HONEYCOMB_CATEGORIES


COST_REQUIRED_COLUMNS = ["商品名称", "营销类别", "成本", "毛利率（%）", "规格"]
EXCLUDED_MARGIN_RANK_CATEGORIES = {"包装费用", "促销礼品"}
BOARD_ALIAS_MAP = {
    "D-FW48G (封边白)": "D-FW48G-4 (封边白)",
    "D-FW48G (封边黑)": "D-FW48G-4 (封边黑)",
}
BOARD_SPEC_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)")
BOARD_THREE_PART_SPEC_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)"
)


def apply_costing(detail: pd.DataFrame, cost_path: str | Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame | float | int]]:
    """为清洗后明细补充成本、毛利和异常信息。"""
    cost_lookup, duplicate_conflicts = _build_cost_lookup(cost_path)
    df = detail.copy()
    df["成本匹配商品名称"] = df["商品名称"].apply(_cost_match_name)
    df["单位成本"] = pd.NA
    df["成本金额"] = pd.NA
    df["毛利额"] = pd.NA
    df["实际毛利率"] = pd.NA
    df["原定毛利率"] = pd.NA
    df["成本状态"] = ""

    for idx, row in df.iterrows():
        match_name = row["成本匹配商品名称"]
        if match_name in duplicate_conflicts:
            df.at[idx, "成本状态"] = "成本冲突"
            continue

        cost_item = cost_lookup.get(match_name)
        if cost_item is None:
            df.at[idx, "成本状态"] = "成本缺失"
            continue

        if row["是否蜂窝板"]:
            unit_cost = cost_item["大板单㎡成本"]
            if pd.isna(unit_cost):
                df.at[idx, "成本状态"] = "大板规格异常"
                continue
            cost_amount = float(row["面积㎡"]) * float(unit_cost)
        else:
            unit_cost = cost_item["单位成本"]
            cost_amount = float(row["已发数量"]) * float(unit_cost)

        amount = float(row["金额"])
        profit = amount - cost_amount
        df.at[idx, "单位成本"] = float(unit_cost)
        df.at[idx, "成本金额"] = cost_amount
        df.at[idx, "毛利额"] = profit
        df.at[idx, "实际毛利率"] = profit / amount if amount else pd.NA
        df.at[idx, "原定毛利率"] = float(cost_item["原定毛利率"]) / 100
        df.at[idx, "成本状态"] = "已计算"

    computed = df[df["成本状态"] == "已计算"].copy()
    missing = df[df["成本状态"] == "成本缺失"].copy()
    abnormal = df[df["成本状态"].isin(["成本冲突", "大板规格异常"])].copy()

    category_margin = _category_margin(computed)
    missing_summary = _issue_summary(missing, "成本缺失")
    abnormal_summary = _issue_summary(abnormal, "成本异常")

    gross_amount = float(df["金额"].sum())
    gross_profit = float(computed["毛利额"].sum()) if not computed.empty else 0.0
    gross_margin_rate = gross_profit / gross_amount if gross_amount else 0.0

    stats = {
        "category_margin_summary": category_margin,
        "missing_cost_summary": missing_summary,
        "cost_exception_summary": abnormal_summary,
        "gross_amount": gross_amount,
        "gross_profit": gross_profit,
        "gross_margin_rate": gross_margin_rate,
        "missing_cost_amount": float(missing["金额"].sum()) if not missing.empty else 0.0,
        "missing_cost_row_count": int(len(missing)),
        "cost_exception_amount": float(abnormal["金额"].sum()) if not abnormal.empty else 0.0,
        "cost_exception_row_count": int(len(abnormal)),
    }
    return df, stats


def _build_cost_lookup(cost_path: str | Path) -> tuple[dict[str, dict[str, float]], set[str]]:
    try:
        raw = pd.read_excel(cost_path, engine="openpyxl")
    except Exception as exc:
        raise AnalysisError(f"成本清单读取失败，请确认文件未损坏且格式为 .xlsx/.xlsm。\n\n错误信息：{exc}") from exc

    missing = [col for col in COST_REQUIRED_COLUMNS if col not in raw.columns]
    if missing:
        raise AnalysisError("成本清单缺少必要字段：\n" + "、".join(missing))

    cost = raw[COST_REQUIRED_COLUMNS].copy()
    cost["商品名称"] = cost["商品名称"].fillna("").astype(str).str.strip()
    cost["营销类别"] = cost["营销类别"].fillna("").astype(str).str.strip()
    cost["规格"] = cost["规格"].fillna("").astype(str).str.strip()
    cost["成本"] = pd.to_numeric(cost["成本"], errors="coerce")
    cost["毛利率（%）"] = pd.to_numeric(cost["毛利率（%）"], errors="coerce")
    cost = cost[(cost["商品名称"] != "") & cost["成本"].notna() & cost["毛利率（%）"].notna()].copy()

    rows = []
    for _, row in cost.iterrows():
        is_board_cost = row["营销类别"] in HONEYCOMB_CATEGORIES
        board_unit_cost = _board_unit_cost(row["成本"], row["规格"]) if is_board_cost else pd.NA
        rows.append(
            {
                "商品名称": row["商品名称"],
                "单位成本": float(row["成本"]),
                "大板单㎡成本": board_unit_cost,
                "原定毛利率": float(row["毛利率（%）"]),
            }
        )

    normalized = pd.DataFrame(rows)
    lookup: dict[str, dict[str, float]] = {}
    duplicate_conflicts: set[str] = set()

    for product, group in normalized.groupby("商品名称"):
        comparable = group.copy()
        comparable["单位成本"] = comparable["单位成本"].round(6)
        comparable["大板单㎡成本"] = comparable["大板单㎡成本"].astype("Float64").round(6)
        comparable["原定毛利率"] = comparable["原定毛利率"].round(6)
        unique_values = comparable.drop_duplicates(["单位成本", "大板单㎡成本", "原定毛利率"])
        if len(unique_values) > 1:
            duplicate_conflicts.add(product)
            continue
        lookup[product] = group.iloc[0].to_dict()

    return lookup, duplicate_conflicts


def _cost_match_name(product_name: object) -> str:
    text = "" if pd.isna(product_name) else str(product_name).strip()
    return BOARD_ALIAS_MAP.get(text, text)


def _board_unit_cost(cost: float, spec: str) -> float | pd.NA:
    text = str(spec).strip()
    if text.lower() == "custom":
        return float(cost)

    three_part = BOARD_THREE_PART_SPEC_PATTERN.search(text)
    if three_part:
        width = float(three_part.group(2))
        length = float(three_part.group(3))
        area = width * length / 1_000_000
        return float(cost) / area if area else pd.NA

    two_part = BOARD_SPEC_PATTERN.search(text)
    if two_part:
        width = float(two_part.group(1))
        length = float(two_part.group(2))
        area = width * length / 1_000_000
        return float(cost) / area if area else pd.NA

    return pd.NA


def _category_margin(computed: pd.DataFrame) -> pd.DataFrame:
    if computed.empty:
        return pd.DataFrame(columns=["营销分类", "销售金额", "成本金额", "毛利额", "毛利率"])

    computed = computed[~computed["营销分类"].isin(EXCLUDED_MARGIN_RANK_CATEGORIES)].copy()
    if computed.empty:
        return pd.DataFrame(columns=["营销分类", "销售金额", "成本金额", "毛利额", "毛利率"])

    summary = (
        computed.groupby("营销分类", as_index=False)
        .agg(销售金额=("金额", "sum"), 成本金额=("成本金额", "sum"), 毛利额=("毛利额", "sum"))
        .sort_values("毛利额", ascending=False)
    )
    summary["毛利率"] = summary.apply(lambda row: row["毛利额"] / row["销售金额"] if row["销售金额"] else 0.0, axis=1)
    return summary.sort_values("毛利率", ascending=False).reset_index(drop=True)


def _issue_summary(df: pd.DataFrame, status_name: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["状态", "营销分类", "商品名称", "行数", "已发数量", "金额"])
    summary = (
        df.groupby(["营销分类", "商品名称"], as_index=False)
        .agg(行数=("商品名称", "size"), 已发数量=("已发数量", "sum"), 金额=("金额", "sum"))
        .sort_values("金额", ascending=False)
    )
    summary.insert(0, "状态", status_name)
    return summary.reset_index(drop=True)
