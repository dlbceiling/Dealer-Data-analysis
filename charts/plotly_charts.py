from html import escape

import plotly.express as px
import plotly.graph_objects as go

from core.models import AnalysisResult


PLOTLY_CONFIG = {
    "displaylogo": False,
    "locale": "zh-CN",
    "responsive": True,
}


def _layout(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        font={"family": "Microsoft YaHei, SimHei, Arial", "size": 13},
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 48, "r": 24, "t": 64, "b": 48},
        hovermode="x unified",
    )
    return fig


def build_chart_html(result: AnalysisResult) -> str:
    figures = [
        monthly_sales_trend(result),
        category_amount_pie(result),
        product_amount_top10(result),
        honeycomb_size_chart(result),
    ]
    chart_blocks = []
    for index, fig in enumerate(figures):
        chart_blocks.append(
            fig.to_html(include_plotlyjs=(index == 0), full_html=False, config=PLOTLY_CONFIG)
        )
    body = "\n".join(chart_blocks)
    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <style>
        body {{
            margin: 0;
            padding: 12px;
            background: #ffffff;
            font-family: "Microsoft YaHei", "SimHei", Arial, sans-serif;
        }}
        .plotly-graph-div {{
            width: 100% !important;
            min-height: 380px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 16px;
        }}
    </style>
</head>
<body>{body}</body>
</html>
"""


def build_report_html(result: AnalysisResult) -> str:
    """用于导出 PDF 的完整报告 HTML。"""
    summary_html = f"""
    <section class="summary">
        <h1>经销商数据分析报告</h1>
        <p>经销商：{result.dealer_name}</p>
        <div class="metrics">
            <div><span>本期总出货金额</span><strong>¥{result.total_amount:,.2f}</strong></div>
            <div><span>蜂窝板总面积</span><strong>{result.total_honeycomb_area:,.2f} ㎡</strong></div>
            <div><span>实际总体毛利额</span><strong>¥{result.gross_profit:,.2f}</strong></div>
            <div><span>实际总体毛利率</span><strong>{result.gross_margin_rate * 100:,.2f}%</strong></div>
        </div>
        <p>成本缺失：{result.missing_cost_row_count} 行，¥{result.missing_cost_amount:,.2f}；成本异常：{result.cost_exception_row_count} 行，¥{result.cost_exception_amount:,.2f}</p>
        <h2>按金额TOP3产品</h2>
        {_table_html(result.top3_products_by_amount, ["商品名称", "金额"])}
        <h2>电器销量TOP3</h2>
        {_table_html(result.heater_top3, ["型号", "已发数量", "金额"])}
        <h2>蜂窝板统计</h2>
        {_table_html(result.honeycomb_summary, ["商品名称", "面积㎡", "金额"])}
        <h2>营销分类毛利率排行</h2>
        {_table_html(result.category_margin_summary, ["营销分类", "销售金额", "成本金额", "毛利额", "毛利率"])}
    </section>
    """
    chart_html = build_chart_html(result)
    return chart_html.replace(
        "<body>",
        """
<body>
<style>
    .summary { padding: 18px 12px 10px; color: #111827; }
    h1 { margin: 0 0 8px; font-size: 26px; }
    h2 { margin: 18px 0 8px; font-size: 18px; }
    .metrics { display: flex; gap: 12px; margin: 14px 0; }
    .metrics div { flex: 1; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
    .metrics span { display: block; color: #6b7280; font-size: 13px; }
    .metrics strong { display: block; margin-top: 6px; font-size: 22px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
    th, td { border: 1px solid #e5e7eb; padding: 7px 9px; text-align: left; }
    th { background: #eef2ff; }
</style>
""" + summary_html,
    )


def _table_html(df, columns: list[str]) -> str:
    if df.empty:
        return "<p>暂无数据</p>"

    rows = []
    for _, row in df.iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if column in {"金额", "销售金额", "成本金额", "毛利额"}:
                value = f"¥{float(value):,.2f}"
            elif column == "毛利率":
                value = f"{float(value) * 100:,.2f}%"
            elif column == "已发数量":
                number = float(value)
                value = f"{int(number):,}" if number.is_integer() else f"{number:,.2f}"
            elif column == "面积㎡":
                value = f"{float(value):,.2f}"
            cells.append(f"<td>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    return "<table><thead><tr>" + header + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def monthly_sales_trend(result: AnalysisResult) -> go.Figure:
    data = result.monthly_trend
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="暂无有效日期数据", showarrow=False, x=0.5, y=0.5)
        fig.update_layout(title="月度进货额趋势")
        return _layout(fig)

    data = data.copy()
    data["年份"] = data["年份"].astype(int).astype(str)
    data["月份"] = data["月份序号"].astype(int)
    fig = px.line(data, x="月份", y="金额", color="年份", markers=True, title="月度进货额趋势")
    fig.update_traces(line={"width": 3}, marker={"size": 8})
    fig.update_yaxes(title="金额")
    fig.update_xaxes(title="月份", tickmode="array", tickvals=list(range(1, 13)), range=[0.7, 12.3])
    return _layout(fig)


def category_amount_pie(result: AnalysisResult) -> go.Figure:
    data = result.category_summary
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="暂无营销分类数据", showarrow=False, x=0.5, y=0.5)
        fig.update_layout(title="营销分类销售额占比")
        return _layout(fig)

    fig = px.pie(data, names="营销分类", values="金额", title="营销分类销售额占比", hole=0.32)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _layout(fig)


def product_amount_top10(result: AnalysisResult) -> go.Figure:
    data = result.product_amount_summary.head(10).sort_values("金额")
    fig = px.bar(data, x="金额", y="商品名称", orientation="h", title="商品金额 TOP10")
    fig.update_xaxes(title="金额")
    fig.update_yaxes(title="商品名称")
    return _layout(fig)


def product_quantity_top10(result: AnalysisResult) -> go.Figure:
    data = result.product_summary.sort_values("已发数量", ascending=False).head(10).sort_values("已发数量")
    fig = px.bar(data, x="已发数量", y="商品名称", orientation="h", title="商品销量 TOP10")
    fig.update_xaxes(title="已发数量")
    fig.update_yaxes(title="商品名称")
    return _layout(fig)


def honeycomb_size_chart(result: AnalysisResult) -> go.Figure:
    data = result.honeycomb_size_summary
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="暂无可解析的蜂窝板尺寸数据", showarrow=False, x=0.5, y=0.5)
        fig.update_layout(title="尺寸统计")
        return _layout(fig)

    fig = px.bar(data, x="尺寸", y="面积㎡", title="尺寸统计")
    fig.update_xaxes(title="尺寸")
    fig.update_yaxes(title="面积㎡")
    return _layout(fig)
