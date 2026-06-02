from pathlib import Path
import tempfile

import pandas as pd
from PySide6.QtCore import QDate, QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from charts.plotly_charts import build_chart_html
from core.analyzer import AnalysisError, analyze_excel
from core.models import AnalysisResult
from export.excel_exporter import export_analysis_result
from ui.widgets import MetricCard


DISPLAY_COLUMNS = [
    "商品名称",
    "营销分类",
    "单位",
    "已发数量",
    "金额",
    "面积㎡",
    "成本金额",
    "毛利额",
    "实际毛利率",
    "单位成本",
    "原定毛利率",
    "成本状态",
    "首单日期",
    "末单日期",
]


class SortableTableItem(QTableWidgetItem):
    """让金额、数量等数字列按数值排序。"""

    def __lt__(self, other):
        left = self.data(Qt.UserRole)
        right = other.data(Qt.UserRole)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return super().__lt__(other)


def fmt_money(value: float) -> str:
    return f"¥{value:,.2f}"


def fmt_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def fmt_area(value: float) -> str:
    return f"{value:,.2f}㎡"


def fmt_percent(value: float) -> str:
    return f"{value * 100:,.2f}%"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("经销商数据分析助手")
        self.resize(1320, 860)

        self.selected_file: Path | None = None
        self.cost_file: Path | None = None
        self.result: AnalysisResult | None = None
        self.filtered_detail = pd.DataFrame()
        self.web_temp_dir = Path(tempfile.gettempdir()) / "dealer_analysis"
        self.web_temp_dir.mkdir(exist_ok=True)
        self.settings = QSettings("DealerAnalysis", "DealerAnalysisAssistant")
        self.cost_file = self._load_default_cost_file()

        self._build_actions()
        self._build_ui()
        self._apply_styles()

    def _build_actions(self) -> None:
        export_action = QAction("导出分析结果", self)
        export_action.triggered.connect(self.export_excel)
        self.toolbar = self.addToolBar("工具")
        self.toolbar.addAction(export_action)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(14)

        title = QLabel("经销商数据分析助手")
        title.setObjectName("AppTitle")
        main_layout.addWidget(title)

        file_bar = QFrame()
        file_bar.setObjectName("FileBar")
        file_layout = QHBoxLayout(file_bar)
        file_layout.setContentsMargins(16, 12, 16, 12)
        file_layout.setSpacing(12)

        self.choose_button = QPushButton("选择Excel文件")
        self.choose_button.clicked.connect(self.choose_file)
        self.file_label = QLabel("未选择文件")
        self.file_label.setObjectName("FileLabel")
        self.choose_cost_button = QPushButton("选择成本清单")
        self.choose_cost_button.clicked.connect(self.choose_cost_file)
        self.cost_file_label = QLabel(self.cost_file.name if self.cost_file else "未选择成本清单")
        self.cost_file_label.setObjectName("FileLabel")
        self.analyze_button = QPushButton("开始分析")
        self.analyze_button.setObjectName("PrimaryButton")
        self.analyze_button.clicked.connect(self.analyze_file)
        self.export_button = QPushButton("导出分析结果")
        self.export_button.clicked.connect(self.export_excel)
        self.export_button.setEnabled(False)

        file_layout.addWidget(self.choose_button)
        file_layout.addWidget(self.file_label, 1)
        file_layout.addWidget(self.choose_cost_button)
        file_layout.addWidget(self.cost_file_label, 1)
        file_layout.addWidget(self.analyze_button)
        file_layout.addWidget(self.export_button)
        main_layout.addWidget(file_bar)

        self.tabs = QTabWidget()
        self.tabs.setVisible(False)
        main_layout.addWidget(self.tabs, 1)

        self.dashboard_tab = self._build_dashboard_tab()
        self.detail_tab = self._build_detail_tab()
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.detail_tab, "明细表")

    def _build_dashboard_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(14)

        self.dealer_label = QLabel("经销商：-\n统计周期：-")
        self.dealer_label.setObjectName("DealerLabel")
        layout.addWidget(self.dealer_label)

        card_grid = QGridLayout()
        card_grid.setSpacing(12)
        self.total_amount_card = MetricCard("本期总出货金额")
        self.top3_card = MetricCard("按金额TOP3产品")
        self.heater_card = MetricCard("电器销量TOP3")
        self.honeycomb_area_card = MetricCard("蜂窝板总面积")
        self.gross_profit_card = MetricCard("实际总体毛利额")
        self.gross_rate_card = MetricCard("实际总体毛利率")
        self.missing_cost_card = MetricCard("成本缺失提示")
        card_grid.addWidget(self.total_amount_card, 0, 0)
        card_grid.addWidget(self.top3_card, 0, 1)
        card_grid.addWidget(self.heater_card, 0, 2)
        card_grid.addWidget(self.honeycomb_area_card, 0, 3)
        card_grid.addWidget(self.gross_profit_card, 1, 0)
        card_grid.addWidget(self.gross_rate_card, 1, 1)
        card_grid.addWidget(self.missing_cost_card, 1, 2, 1, 2)
        layout.addLayout(card_grid)

        table_splitter = QSplitter(Qt.Horizontal)
        self.top3_table = self._create_small_table(["商品名称", "金额"])
        self.heater_table = self._create_small_table(["型号", "数量", "金额"])
        self.honeycomb_table = self._create_small_table(["商品名称", "面积㎡", "金额"])
        table_splitter.addWidget(self._wrap_table("按金额TOP3产品", self.top3_table))
        table_splitter.addWidget(self._wrap_table("电器销量TOP3", self.heater_table))
        table_splitter.addWidget(self._wrap_table("蜂窝板统计", self.honeycomb_table))
        layout.addWidget(table_splitter)

        self.margin_table = self._create_small_table(["营销分类", "销售金额", "成本金额", "毛利额", "毛利率"])
        layout.addWidget(self._wrap_table("营销分类毛利率排行", self.margin_table))

        self.chart_view = QWebEngineView()
        self.chart_view.setMinimumHeight(1980)
        layout.addWidget(self.chart_view)
        return scroll

    def _build_detail_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        filters = QGroupBox("筛选")
        filter_layout = QHBoxLayout(filters)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索商品")
        self.search_input.textChanged.connect(self.apply_filters)
        self.category_combo = QComboBox()
        self.category_combo.currentTextChanged.connect(self.apply_filters)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.dateChanged.connect(self.apply_filters)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.dateChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("商品"))
        filter_layout.addWidget(self.search_input, 2)
        filter_layout.addWidget(QLabel("营销分类"))
        filter_layout.addWidget(self.category_combo, 1)
        filter_layout.addWidget(QLabel("开始日期"))
        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(QLabel("结束日期"))
        filter_layout.addWidget(self.end_date)
        layout.addWidget(filters)

        self.detail_table = QTableWidget()
        self.detail_table.setSortingEnabled(True)
        self.detail_table.setAlternatingRowColors(True)
        self.detail_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.detail_table, 1)
        return page

    def choose_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Excel文件",
            "",
            "Excel 文件 (*.xlsx *.xlsm)",
        )
        if not file_path:
            return
        self.selected_file = Path(file_path)
        self.file_label.setText(self.selected_file.name)

    def choose_cost_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择成本清单",
            "",
            "Excel 文件 (*.xlsx *.xlsm)",
        )
        if not file_path:
            return
        self.cost_file = Path(file_path)
        self.cost_file_label.setText(self.cost_file.name)
        self.settings.setValue("cost_file", str(self.cost_file))

    def _load_default_cost_file(self) -> Path | None:
        saved_cost_file = self.settings.value("cost_file", "", str)
        if saved_cost_file and Path(saved_cost_file).exists():
            return Path(saved_cost_file)

        default_names = ["全sku成本明细.xlsx", "全SKU成本明细.xlsx"]
        search_roots = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.cwd(),
        ]
        for root in search_roots:
            if not root.exists():
                continue
            for file_name in default_names:
                direct_file = root / file_name
                if direct_file.exists():
                    self.settings.setValue("cost_file", str(direct_file))
                    return direct_file
            for file_name in default_names:
                matches = [path for path in root.rglob(file_name) if not path.name.startswith("~$")]
                if matches:
                    self.settings.setValue("cost_file", str(matches[0]))
                    return matches[0]
        return None

    def analyze_file(self) -> None:
        if not self.selected_file:
            QMessageBox.warning(self, "提示", "请先选择 Excel 文件。")
            return

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self.analyze_button.setEnabled(False)
        try:
            self.result = analyze_excel(self.selected_file, self.cost_file)
            self._render_result()
        except AnalysisError as exc:
            QMessageBox.critical(self, "分析失败", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "分析失败", f"发生未知错误：{exc}")
        finally:
            self.analyze_button.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def _render_result(self) -> None:
        if self.result is None:
            return

        self.tabs.setVisible(True)
        self.export_button.setEnabled(True)
        self.dealer_label.setText(
            f"经销商：{self.result.dealer_name}\n"
            f"统计周期：{self._period_text()}"
        )
        self.total_amount_card.set_value(fmt_money(self.result.total_amount))
        self.top3_card.set_value(self._card_lines(self.result.top3_products_by_amount, "金额"))
        self.heater_card.set_value(self._heater_lines())
        self.honeycomb_area_card.set_value(fmt_area(self.result.total_honeycomb_area))
        self.gross_profit_card.set_value(fmt_money(self.result.gross_profit) if self.cost_file else "未选择成本清单")
        self.gross_rate_card.set_value(fmt_percent(self.result.gross_margin_rate) if self.cost_file else "未选择成本清单")
        self.missing_cost_card.set_value(self._missing_cost_text())

        self._fill_table(self.top3_table, self.result.top3_products_by_amount, ["商品名称", "金额"])
        self._fill_table(self.heater_table, self.result.heater_top3, ["型号", "已发数量", "金额"], aliases=["型号", "数量", "金额"])
        self._fill_table(self.honeycomb_table, self.result.honeycomb_summary, ["商品名称", "面积㎡", "金额"])
        self._fill_table(
            self.margin_table,
            self.result.category_margin_summary,
            ["营销分类", "销售金额", "成本金额", "毛利额", "毛利率"],
        )
        self._load_html(self.chart_view, build_chart_html(self.result), "charts.html")
        self._reset_filters()
        self.apply_filters()

    def _reset_filters(self) -> None:
        if self.result is None:
            return
        df = self.result.clean_detail
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("全部")
        for category in sorted([c for c in df["营销分类"].dropna().unique().tolist() if c]):
            self.category_combo.addItem(category)
        self.category_combo.blockSignals(False)

        valid_dates = df["单据日期"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
        else:
            min_date = max_date = pd.Timestamp.today().date()

        self.start_date.blockSignals(True)
        self.end_date.blockSignals(True)
        self.start_date.setDate(QDate(min_date.year, min_date.month, min_date.day))
        self.end_date.setDate(QDate(max_date.year, max_date.month, max_date.day))
        self.start_date.blockSignals(False)
        self.end_date.blockSignals(False)
        self.search_input.clear()

    def apply_filters(self) -> None:
        if self.result is None:
            return
        df = self.result.clean_detail.copy()
        keyword = self.search_input.text().strip()
        category = self.category_combo.currentText()
        start = pd.Timestamp(self.start_date.date().toPython())
        end = pd.Timestamp(self.end_date.date().toPython()) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        if keyword:
            df = df[df["商品名称"].str.contains(keyword, case=False, na=False)]
        if category and category != "全部":
            df = df[df["营销分类"] == category]
        if "单据日期" in df.columns:
            df = df[df["单据日期"].isna() | ((df["单据日期"] >= start) & (df["单据日期"] <= end))]

        self.filtered_detail = df
        self._fill_detail_table(self._aggregate_detail(df))

    def _aggregate_detail(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=DISPLAY_COLUMNS)

        rows = []
        has_cost_columns = "成本金额" in df.columns

        for product_name, group in df.groupby("商品名称", sort=False):
            row = {
                "商品名称": product_name,
                "营销分类": "、".join(sorted({str(v) for v in group["营销分类"] if str(v)})),
                "单位": "、".join(sorted({str(v) for v in group["单位"] if str(v)})),
                "已发数量": group["已发数量"].sum(),
                "金额": group["金额"].sum(),
                "面积㎡": group["面积㎡"].sum(),
                "首单日期": group["单据日期"].min(),
                "末单日期": group["单据日期"].max(),
            }

            if has_cost_columns:
                statuses = {str(v) for v in group["成本状态"] if str(v)}
                computed_group = group[group["成本状态"] == "已计算"].copy()
                has_computed = not computed_group.empty
                has_missing = "成本缺失" in statuses
                has_abnormal = bool(statuses.intersection({"成本冲突", "大板规格异常"}))

                if has_computed:
                    row["成本金额"] = pd.to_numeric(computed_group["成本金额"], errors="coerce").sum()
                    row["毛利额"] = pd.to_numeric(computed_group["毛利额"], errors="coerce").sum()
                    row["单位成本"] = pd.to_numeric(computed_group["单位成本"], errors="coerce").mean()
                    row["原定毛利率"] = pd.to_numeric(computed_group["原定毛利率"], errors="coerce").mean()
                    row["实际毛利率"] = row["毛利额"] / row["金额"] if row["金额"] else pd.NA
                else:
                    row["成本金额"] = pd.NA
                    row["毛利额"] = pd.NA
                    row["单位成本"] = pd.NA
                    row["原定毛利率"] = pd.NA
                    row["实际毛利率"] = pd.NA

                if has_computed and (has_missing or has_abnormal):
                    status_parts = ["部分成本缺失" if has_missing else "部分成本异常"]
                    if has_missing and has_abnormal:
                        status_parts.append("部分成本异常")
                    row["成本状态"] = "、".join(status_parts)
                elif has_computed:
                    row["成本状态"] = "已计算"
                elif has_missing and has_abnormal:
                    row["成本状态"] = "不可计算（成本缺失、成本异常）"
                elif has_missing:
                    row["成本状态"] = "不可计算（成本缺失）"
                elif has_abnormal:
                    row["成本状态"] = "不可计算（成本异常）"
                else:
                    row["成本状态"] = ""

            rows.append(row)

        summary = pd.DataFrame(rows)
        return summary.sort_values("金额", ascending=False).reset_index(drop=True)

    def export_excel(self) -> None:
        if self.result is None:
            QMessageBox.information(self, "提示", "请先完成分析。")
            return
        default_name = f"{self.result.dealer_name}_分析结果.xlsx"
        output_path, _ = QFileDialog.getSaveFileName(self, "导出分析结果", default_name, "Excel 文件 (*.xlsx)")
        if not output_path:
            return
        try:
            export_analysis_result(self.result, output_path)
            QMessageBox.information(self, "导出完成", f"已导出：\n{output_path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"导出 Excel 失败：{exc}")

    def _load_html(self, view: QWebEngineView, html: str, file_name: str) -> None:
        html_path = self.web_temp_dir / file_name
        html_path.write_text(html, encoding="utf-8")
        view.load(QUrl.fromLocalFile(str(html_path)))

    def _fill_detail_table(self, df: pd.DataFrame) -> None:
        columns = [col for col in DISPLAY_COLUMNS if col in df.columns]
        self.detail_table.setSortingEnabled(False)
        self.detail_table.clear()
        self.detail_table.setColumnCount(len(columns))
        self.detail_table.setRowCount(len(df))
        self.detail_table.setHorizontalHeaderLabels(columns)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, column in enumerate(columns):
                item = SortableTableItem(self._format_cell(row[column], column))
                if column in {"已发数量", "单价", "金额", "面积㎡", "单位成本", "成本金额", "毛利额", "实际毛利率", "原定毛利率"}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if isinstance(row[column], (int, float)) and pd.notna(row[column]):
                        item.setData(Qt.UserRole, float(row[column]))
                self.detail_table.setItem(row_idx, col_idx, item)

        self.detail_table.resizeColumnsToContents()
        self.detail_table.setSortingEnabled(True)

    def _fill_table(self, table: QTableWidget, df: pd.DataFrame, columns: list[str], aliases: list[str] | None = None) -> None:
        aliases = aliases or columns
        table.clear()
        table.setColumnCount(len(columns))
        table.setRowCount(len(df))
        table.setHorizontalHeaderLabels(aliases)
        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, column in enumerate(columns):
                item = SortableTableItem(self._format_cell(row[column], column))
                if column in {"已发数量", "单价", "金额", "面积㎡", "销售金额", "成本金额", "毛利额", "毛利率"}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setData(Qt.UserRole, float(row[column]) if pd.notna(row[column]) else 0.0)
                table.setItem(row_idx, col_idx, item)
        table.resizeColumnsToContents()

    def _create_small_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(160)
        return table

    def _wrap_table(self, title: str, table: QTableWidget) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(table)
        return box

    def _card_lines(self, df: pd.DataFrame, value_column: str) -> str:
        if df.empty:
            return "暂无数据"
        return "\n".join(f"{row['商品名称']}：{fmt_money(row[value_column])}" for _, row in df.iterrows())

    def _heater_lines(self) -> str:
        if self.result is None or self.result.heater_top3.empty:
            return "暂无电器数据"
        return "\n".join(
            f"{row['型号']}：{fmt_number(row['已发数量'])}，{fmt_money(row['金额'])}"
            for _, row in self.result.heater_top3.iterrows()
        )

    def _missing_cost_text(self) -> str:
        if self.result is None:
            return "-"
        if not self.cost_file:
            return "选择成本清单后计算"
        lines = [
            f"缺失 {self.result.missing_cost_row_count} 行，{fmt_money(self.result.missing_cost_amount)}",
        ]
        if self.result.cost_exception_row_count:
            lines.append(f"异常 {self.result.cost_exception_row_count} 行，{fmt_money(self.result.cost_exception_amount)}")
        if not self.result.missing_cost_row_count and not self.result.cost_exception_row_count:
            return "无成本缺失/异常"
        return "\n".join(lines)

    def _period_text(self) -> str:
        if self.result is None:
            return "-"
        if self.result.period_start is None or self.result.period_end is None:
            return f"无有效日期（共{self.result.source_row_count}条）"
        start_text = pd.Timestamp(self.result.period_start).strftime("%Y-%m-%d")
        end_text = pd.Timestamp(self.result.period_end).strftime("%Y-%m-%d")
        return f"{start_text} ～ {end_text}（共{self.result.source_row_count}条）"

    def _format_cell(self, value, column: str) -> str:
        if pd.isna(value):
            if column in {"成本金额", "毛利额", "实际毛利率"}:
                return "不可计算"
            return ""
        if column in {"金额", "单价", "销售金额", "成本金额", "毛利额", "单位成本"}:
            return fmt_money(float(value))
        if column in {"实际毛利率", "原定毛利率", "毛利率"}:
            return fmt_percent(float(value))
        if column == "面积㎡":
            return f"{float(value):,.2f}"
        if column == "已发数量":
            return fmt_number(float(value))
        if column in {"单据日期", "首单日期", "末单日期"}:
            try:
                return pd.Timestamp(value).strftime("%Y-%m-%d")
            except Exception:
                return str(value)
        return str(value)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f6f7f9; color: #111827; font-family: "Microsoft YaHei"; font-size: 14px; }
            #AppTitle { font-size: 28px; font-weight: 700; color: #111827; padding: 4px 0; }
            #FileBar, #MetricCard, QGroupBox { background: white; border: 1px solid #e5e7eb; border-radius: 8px; }
            #FileLabel { color: #4b5563; }
            QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 14px; }
            QPushButton:hover { background: #f1f5f9; }
            QPushButton:disabled { color: #9ca3af; background: #f3f4f6; }
            #PrimaryButton { background: #2563eb; color: white; border-color: #2563eb; font-weight: 600; }
            #PrimaryButton:hover { background: #1d4ed8; }
            #DealerLabel { font-size: 17px; font-weight: 600; line-height: 150%; background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px; }
            #MetricTitle { color: #6b7280; font-size: 13px; }
            #MetricValue { color: #111827; font-size: 20px; font-weight: 700; }
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #e5e7eb; padding: 8px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }
            QTabBar::tab:selected { background: white; font-weight: 600; }
            QTableWidget { background: white; border: 1px solid #e5e7eb; gridline-color: #edf2f7; alternate-background-color: #f9fafb; }
            QHeaderView::section { background: #eef2ff; color: #1f2937; padding: 7px; border: 0; font-weight: 600; }
            QLineEdit, QComboBox, QDateEdit { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 7px; }
            QGroupBox { margin-top: 10px; padding: 12px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            """
        )
