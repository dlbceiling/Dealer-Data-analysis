from dataclasses import dataclass

import pandas as pd


@dataclass
class AnalysisResult:
    """一次 Excel 分析后的全部结果。"""

    dealer_name: str
    clean_detail: pd.DataFrame
    product_summary: pd.DataFrame
    product_amount_summary: pd.DataFrame
    category_summary: pd.DataFrame
    heater_top3: pd.DataFrame
    top3_products_by_amount: pd.DataFrame
    honeycomb_summary: pd.DataFrame
    honeycomb_size_summary: pd.DataFrame
    monthly_trend: pd.DataFrame
    total_amount: float
    total_honeycomb_area: float
    period_start: pd.Timestamp | None
    period_end: pd.Timestamp | None
    source_row_count: int
    ignored_detail: pd.DataFrame
    category_margin_summary: pd.DataFrame
    missing_cost_summary: pd.DataFrame
    cost_exception_summary: pd.DataFrame
    gross_amount: float
    gross_profit: float
    gross_margin_rate: float
    missing_cost_amount: float
    missing_cost_row_count: int
    cost_exception_amount: float
    cost_exception_row_count: int
