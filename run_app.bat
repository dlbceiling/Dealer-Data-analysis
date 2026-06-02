@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"

echo Starting Dealer Analysis Assistant...
echo.

if exist "%PYTHON%" (
    set "BOOTSTRAP_PYTHON=%PYTHON%"
) else (
    set "BOOTSTRAP_PYTHON=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%BOOTSTRAP_PYTHON%" -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

echo Installing dependencies...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 goto :error

echo.
echo Launching application...
python main.py
goto :end

:error
echo.
echo Startup failed. Please confirm Python 3.14 is installed.
pause

:end
endlocal
