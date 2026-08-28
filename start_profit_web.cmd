@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo  Hanamans Profit Tool Web - startup
echo ==================================================

set "PYTHON=.venv\Scripts\python.exe"
set "STAMP=.venv\requirements.txt.stamp"
set "INSTALL=0"

if not exist "%PYTHON%" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv .venv || goto :error
    set "INSTALL=1"
)

if not exist "%STAMP%" set "INSTALL=1"
if exist "%STAMP%" fc /b requirements.txt "%STAMP%" >nul 2>&1 || set "INSTALL=1"
"%PYTHON%" -c "import django, dotenv" >nul 2>&1 || set "INSTALL=1"

if "%INSTALL%"=="1" (
    echo [SETUP] Installing required Python packages...
    "%PYTHON%" -m pip install -r requirements.txt || goto :error
    copy /y requirements.txt "%STAMP%" >nul || goto :error
) else (
    echo [SETUP] Required Python packages are already installed.
)

if not exist .env (
    if exist .env.example copy /y .env.example .env >nul
    echo.
    echo eBay integration requires these values in .env:
    echo   EBAY_CLIENT_ID
    echo   EBAY_CLIENT_SECRET
    echo   EBAY_RUNAME
    echo The Web calculator can still be used without eBay settings.
    echo.
)

echo [SETUP] Applying database migrations...
"%PYTHON%" manage.py migrate || goto :error
echo [SETUP] Running Django system checks...
"%PYTHON%" manage.py check || goto :error

echo.
echo Hanamans Profit Tool Web
echo.
echo PC:
echo   http://127.0.0.1:8001/
echo Monthly Profit:
echo   http://127.0.0.1:8001/monthly/
echo Same LAN phone/Chromebook:
echo   http://^<PC-IP^>:8001/
echo.
echo Separate ports allow both tools to run together:
echo   SKU Master  = 8000
echo   Profit Tool = 8001
echo.
echo Press Ctrl+C to stop the server.
"%PYTHON%" manage.py runserver 0.0.0.0:8001
goto :eof

:error
echo.
echo [ERROR] Startup failed. Review the message above and try again.
pause
exit /b 1
