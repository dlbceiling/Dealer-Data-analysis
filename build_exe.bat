@echo off
chcp 65001 >nul
cd /d %~dp0

set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

if not exist .venv (
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 (
        echo 创建虚拟环境失败，请确认 Python 3.14 已正确安装。
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "经销商数据分析助手" ^
  --hidden-import PySide6.QtWebEngineCore ^
  --hidden-import PySide6.QtWebEngineWidgets ^
  --collect-all PySide6 ^
  --collect-all plotly ^
  main.py

echo.
echo 打包完成后，exe 位于 dist\经销商数据分析助手\经销商数据分析助手.exe
pause
