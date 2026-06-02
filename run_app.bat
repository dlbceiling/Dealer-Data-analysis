@echo off
chcp 65001 >nul

set PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe

echo 正在启动经销商数据分析助手...
echo.

if not exist ".venv" (
    echo 首次运行，正在创建虚拟环境...
    "%PYTHON%" -m venv .venv
)

call .venv\Scripts\activate.bat

echo 检查依赖...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo 启动程序...
python main.py

pause