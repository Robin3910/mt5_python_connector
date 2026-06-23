@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

echo ========================================
echo   MT5 Python Connector 启动脚本
echo ========================================
echo.

echo [1/2] 正在安装依赖，请稍候...
call :wait_dots
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络连接或 requirements.txt
    pause
    exit /b 1
)
echo.
echo [2/2] 依赖安装完成，正在启动服务...
python app.py
goto :end

:wait_dots
setlocal enabledelayedexpansion
set "dots="
for /L %%i in (1,1,10) do (
    <nul set /p "=."
    ping ::1 -n 1 -w 1000 >nul 2>&1
)
endlocal
exit /b 0

:end
pause
