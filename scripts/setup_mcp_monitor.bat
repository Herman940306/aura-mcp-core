@echo off
REM KIRO_MCP Monitor Setup Script
REM Project Creator: Herman Swanepoel
REM This script sets up the MCP Monitor and creates a desktop shortcut

title KIRO_MCP Monitor Setup

echo.
echo ================================================================================
echo   KIRO_MCP MONITOR SETUP
echo ================================================================================
echo.
echo   Project Creator: Herman Swanepoel
echo   Version: 1.0
echo.
echo ================================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found!
        echo Please install Python from https://www.python.org/
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

echo [1/4] Python found: %PYTHON_CMD%
echo.

REM Install required packages
echo [2/4] Installing required packages...
%PYTHON_CMD% -m pip install requests psutil Pillow --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Some packages may not have installed correctly
) else (
    echo       Packages installed successfully
)
echo.

REM Create icon
echo [3/4] Creating monitor icon...
%PYTHON_CMD% create_icon.py
echo.

REM Create desktop shortcuts
echo [4/4] Creating desktop shortcuts...
powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1
powershell -ExecutionPolicy Bypass -File create_html_dashboard_shortcut.ps1
echo.

echo ================================================================================
echo   SETUP COMPLETE!
echo ================================================================================
echo.
echo   The KIRO_MCP Monitor has been installed successfully.
echo.
echo   You can now:
echo   1. Double-click "KIRO_MCP Dashboard" (HTML) on your desktop
echo   2. Double-click "KIRO_MCP Monitor" (Terminal) on your desktop
echo   3. Run "launch_mcp_monitor.bat" from this folder
echo   4. Open "mcp_monitor_dashboard.html" in your browser
echo.
echo   Recommended: Use the HTML Dashboard for best experience!
echo.
echo ================================================================================
echo.

pause
