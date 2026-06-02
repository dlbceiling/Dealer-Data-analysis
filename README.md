# 经销商数据分析助手

Windows 本地桌面工具，使用 PySide6 + Pandas + openpyxl + Plotly 实现。

## 项目结构

```text
dealer_analysis/
    main.py
    core/
        analyzer.py
        models.py
    charts/
        plotly_charts.py
    export/
        excel_exporter.py
    ui/
        main_window.py
        widgets.py
    requirements.txt
    run_app.bat
    build_exe.bat
```

## 运行方式

1. 安装 Python 3.14。
2. 进入本目录。
3. 双击 `run_app.bat`。

`run_app.bat` 会自动：

- 优先使用默认安装路径 `C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe`
- 如果默认路径不存在，再尝试调用 `PATH` 里的 `python`
- 首次运行时自动创建 `.venv`
- 自动安装依赖并启动程序

也可以在命令行运行：

```bat
cd /d 项目目录
run_app.bat
```

如果需要手动启动，也可以使用：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python main.py
```

## 打包成 exe

双击 `build_exe.bat`。

打包完成后，程序在：

```text
dist\经销商数据分析助手\经销商数据分析助手.exe
```

## Excel 格式

第一行必须是字段名，必要字段为：

```text
经销商名称
单据日期
营销分类
商品名称
单位
已发数量
单价
金额
尺寸
```

其他字段会自动忽略。

## 规则说明

- 商品按“商品名称”归并，统计已发数量和金额。
- 金额负数会正常参与统计。
- 单据日期会转换为日期，并生成日、周、月字段。
- 营销分类为 `A/X/Z/T/S/J/G/D+/C/S系列` 时按取暖器统计。
- 营销分类为 `7mm大板/9mm大板` 时按蜂窝板统计。
- 蜂窝板尺寸只解析 `数字*数字` 格式，例如 `2000*1000`。
- 蜂窝板面积公式：长 × 宽 ÷ 1000000 × 已发数量。
