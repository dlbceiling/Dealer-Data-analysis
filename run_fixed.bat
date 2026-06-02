@echo off

set PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe

echo ÕýÔÚÆô¶¯...
echo.

if not exist ".venv" (
    "%PYTHON%" -m venv .venv
)

call .venv\Scripts\activate.bat

python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

python main.py

pause