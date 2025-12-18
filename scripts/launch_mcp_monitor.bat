@echo off
REM KIRO_MCP Monitor Launcher
REM Project Creator: Herman Swanepoel
REM Version: 1.0

title KIRO_MCP Monitor Dashboard

echo.
echo ========================================
echo   KIRO_MCP Monitor Dashboard
echo ========================================
echo.
echo Starting monitor...
echo.

REM Try to find Python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python mcp_monitor_dashboard.py
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        py mcp_monitor_dashboard.py
    ) else (
        echo ERROR: Python not found!
        echo Please install Python or add it to PATH.
        pause
        exit /b 1
    )
)

pause
