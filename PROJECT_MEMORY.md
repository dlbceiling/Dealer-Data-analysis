# 经销商数据分析助手项目记忆

更新时间：2026-06-04

本文档用于记录开发过程中的关键上下文、决策、文件位置、验证数据和后续注意事项。它不是业务规则全集；完整业务规则见 `PROJECT_CONTEXT.md`，项目状态见 `PROJECT_STATUS.md`。

## 1. 项目基本信息

- 项目名称：经销商数据分析助手。
- 项目路径：

```text
C:\Users\Administrator\Documents\New project\dealer_analysis
```

- 当前开发环境：
  - Windows
  - PowerShell
  - Python 3.14
  - 虚拟环境：`.venv`
- 运行脚本：

```text
run_app.bat
```

- 打包脚本：

```text
build_exe.bat
```

## 2. 重要文档

当前项目已有三份项目文档：

```text
README.md
PROJECT_STATUS.md
PROJECT_CONTEXT.md
PROJECT_MEMORY.md
```

用途：

- `README.md`：给使用者看的运行、打包、基础说明。
- `PROJECT_STATUS.md`：当前项目状态、已完成/未完成/BUG/计划。
- `PROJECT_CONTEXT.md`：完整业务规则上下文。
- `PROJECT_MEMORY.md`：开发记忆和交接备忘。

后续修改业务规则时，优先同步更新：

```text
PROJECT_CONTEXT.md
PROJECT_STATUS.md
PROJECT_MEMORY.md
```

## 3. 核心代码文件

```text
main.py
```

- 应用入口。
- 创建 QApplication 和 MainWindow。

```text
core/analyzer.py
```

- 经销商出货 Excel 读取。
- 数据清洗。
- 商品、营销分类、蜂窝板、电器、月度趋势等核心分析。
- 剔除 `7mm大板` 中 `标准板/标准版` 数据。
- 调用成本模块。

```text
core/costing.py
```

- 成本清单读取。
- 成本匹配。
- 大板单㎡成本计算。
- 毛利额、毛利率计算。
- 成本缺失、成本异常识别。
- 营销分类毛利排行。
- 大板别名映射目前写在这里。

```text
core/models.py
```

- `AnalysisResult` 数据类。
- 所有分析结果字段都集中在这里。

```text
charts/plotly_charts.py
```

- Plotly 图表。
- PDF 报告 HTML。
- 已取消商品销量 TOP10 图表。

```text
ui/main_window.py
```

- PySide6 主界面。
- 文件选择、成本文件自动调用、Dashboard、明细页、导出按钮。
- 明细页按商品名称合并后展示。

```text
ui/widgets.py
```

- Dashboard 指标卡片组件。

```text
export/excel_exporter.py
```

- 分析结果 Excel 导出。

## 4. 外部数据文件记忆

当前开发验证使用过的经销商出货文件：

```text
C:\Users\Administrator\Desktop\AI数据分析\上虞经销商25年至今出货数据.xlsx
```

当前成本清单文件：

```text
C:\Users\Administrator\Desktop\全sku成本明细.xlsx
```

成本清单自动调用逻辑：

- 优先读取上次选择过的成本文件路径。
- 若无历史记录，自动查找：
  - 桌面
  - 文档目录
  - 当前项目目录
- 文件名识别：

```text
全sku成本明细.xlsx
全SKU成本明细.xlsx
```

## 5. 当前已验证结果

使用上虞经销商数据和全 SKU 成本清单验证过：

```text
原始出货行数：1117
剔除 7mm 大板标准板/标准版：1 行
参与分析行数：1116
```

毛利验证结果曾跑出：

```text
本期总出货金额：¥400,256.43
实际总体毛利额：¥163,274.90
实际总体毛利率：40.79%
成本缺失：43 行，¥4,671.11
成本异常：0 行
```

电器销量验证：

```text
DB306-FHZ-A5      89
DB306-FHZ-A8L     70
DB100-FH-C2       66
JS2               64
```

注意：

- `JS2 = 64` 已与用户人工计算一致。
- JS2 因数量排第 4，所以不会出现在电器 TOP3。

商品金额合并验证：

```text
D-FW48G-4        ¥87,983.44
DB306-FHZ-A5     ¥46,229.00
DB306-FHZ-A8L    ¥45,276.00
```

## 6. 关键业务决策记忆

### 6.1 成本缺失口径

用户确认：

- 成本缺失商品不按 0 成本计算。
- 毛利显示为无法计算。
- 销售额仍进入总体销售额展示。
- Dashboard 显示缺失行数和缺失金额。
- 成本缺失清单导出，方便用户补充成本。

当前实现：

- 总体销售额分母包含全部当前分析销售额。
- 总体毛利额只累加已成功计算成本的行。

补充规则：

- `营销分类 = 售后配件` 且成本缺失时，不再按普通“成本缺失”处理。
- 该类记录按 `单价 × 已发数量 × 90%` 估算实际成本。
- 成本状态记为 `售后配件估算成本`，并参与毛利计算。

### 6.2 成本冲突口径

用户确认：

- 同商品名如果成本冲突，优先报错/标记异常。
- 不静默选一条。
- 该商品毛利不计算。
- 导出 `成本异常清单`。

### 6.3 大板成本口径

用户确认：

- 大板成本表 `custom` 表示成本就是单㎡成本。
- 两段规格如 `1220×2440` 用长宽换算面积。
- 三段规格如 `7×600×1200` 取后两段算面积。
- 经销商大板成本使用销售表 `尺寸` 计算出的实际出货面积。
- 成本表规格只用于换算单㎡成本。

补充规则：

- `7mm大板/9mm大板` 中尾缀带 `（修边）` 的商品属于整板产品。
- 整板产品与同型号但不带 `（修边）` 的商品成本口径不同，需要单独录入整板成本。
- 整板成本匹配时，需按 `商品名称 + 规格` 精确匹配。
- `D-FW48G (修边)` 视同 `D-FW48G-04 (修边)`。
- 若销售规格为 `1220×3600` 或 `1220×3000` 且成本表未录入，则暂回退到 `1220×2440` 的整板成本。
- 销售侧尺寸解析已扩展到 `×` 和三段式尺寸，便于整板面积换算。
- 当前先忽略营销分类名称后缀为 `实芯板` 的数据，后续再单独处理。

### 6.4 大板别名口径

用户确认：

```text
D-FW48G (封边白) = D-FW48G-4 (封边白)
D-FW48G (封边黑) = D-FW48G-4 (封边黑)
```

原因：

- 产品线升级后更名，原 D-FW48G 改名为 D-FW48G-4。

当前别名写在：

```text
core/costing.py
BOARD_ALIAS_MAP
```

### 6.5 标准板忽略口径

用户确认：

- `7mm大板` 中包含 `标准板/标准版` 的产品已淘汰。
- 分析时直接删除，不统计、不分析。
- 导出到 `已忽略数据`。

### 6.6 电器/取暖器口径

用户修正过多次，当前最终口径：

- `A/J/...系列` 形式也要识别为电器/取暖器。
- `凉霸` 也计入电器。
- `DB100-FH-JS2`、`DB100-FS-JS2` 统一归并为 `JS2`。
- `延长件` 中的 JS2 型材不计入电器销量。

### 6.7 毛利排行排除项

用户确认：

- `包装费用`
- `促销礼品`

不参与营销分类毛利率排行。

但它们仍参与总销售额和总体毛利计算。

### 6.8 图表口径

用户确认：

- 月度趋势横轴只显示 1-12 月。
- 跨年份用不同颜色折线对比。
- 商品销量 TOP10 取消。
- 商品金额 TOP10 去掉括号内备注后合并。

### 6.9 明细页口径

用户确认：

- 明细页展示按 `商品名称` 相同合并后的结果。
- 不再展示所有原始流水数据。

当前实现：

- 先筛选原始明细。
- 再按 `商品名称` 汇总展示。

## 7. 当前项目结构注意事项

当前目录中存在 `.venv/`：

- 这是本机虚拟环境。
- 不应复制到源码仓库。
- 换电脑开发时应重新创建虚拟环境。

当前目录中存在调试 CSV：

```text
_cost_duplicate_conflicts.csv
_cost_unmatched_non_board.csv
_matched_products.csv
```

这些文件是开发验证产物，不是应用必需文件。

建议后续：

- 删除。
- 或移动到 `debug/` 目录。
- 或在正式交付前排除。

## 8. 运行方式记忆

推荐运行：

```bat
run_app.bat
```

手动运行：

```bat
.venv\Scripts\activate
python main.py
```

如新电脑没有 `.venv`：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python main.py
```

## 9. 打包方式记忆

打包：

```bat
build_exe.bat
```

打包结果目录：

```text
dist\经销商数据分析助手\
```

给其他电脑使用时：

- 复制整个 `dist\经销商数据分析助手\` 文件夹。
- 不要只复制 exe。
- 另一台电脑不需要安装 Python。

继续开发时：

- 复制源码目录 `dealer_analysis/`。
- 不要基于 `dist/` 开发。

## 10. 常用验证命令

语法检查：

```bat
.venv\Scripts\python.exe -m py_compile main.py core\__init__.py core\analyzer.py core\costing.py core\models.py charts\__init__.py charts\plotly_charts.py export\__init__.py export\excel_exporter.py ui\__init__.py ui\widgets.py ui\main_window.py
```

真实数据分析验证时，常用文件：

```text
C:\Users\Administrator\Desktop\AI数据分析\上虞经销商25年至今出货数据.xlsx
C:\Users\Administrator\Desktop\全sku成本明细.xlsx
```

## 11. 已知技术注意点

- PowerShell 管道中直接写中文字符串时，偶尔会因编码造成测试脚本 KeyError。
- 测试脚本中建议用 Unicode 转义或从 Excel 列名自动读取，避免控制台编码问题。
- Qt WebEngine 的 Plotly HTML 内容较大，当前实现使用临时 HTML 文件加载，比直接 `setHtml` 稳定。
- PDF 导出是异步任务，当前提示是“任务已提交”，不是严格的完成回调。

## 12. 后续开发优先事项

建议下一步优先级：

1. 清理调试文件和无明确用途的 `run_fixed.bat`。
2. 将大板别名映射从代码移到配置文件，方便业务维护。
3. 增加“原始流水”页签，方便从商品汇总追溯到原始记录。
4. 增加成本缺失清单的界面入口，而不仅是导出。
5. 更新 `README.md`，把最新成本和毛利规则写进去。
6. 重新打包 exe，并在另一台 Windows 电脑验证运行。

## 13. 修改时最容易踩坑的点

- 不要把成本缺失当作 0 成本。
- 不要让 `包装费用`、`促销礼品` 出现在毛利率排行中。
- 不要把 `7mm大板` 的标准板/标准版纳入任何统计。
- 商品金额 TOP10 是括号截断后合并，商品汇总和明细页是原始商品名称精确合并。
- 电器 TOP3 是按合并型号数量排行，不是按金额排行。
- JS2 的特殊归并不能丢。
- 大板销售成本必须用销售表 `尺寸` 算实际出货面积，不能直接用成本表规格面积。
