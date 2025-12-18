@echo off
REM KIRO_MCP Dashboard Launcher
REM Project Creator: Herman Swanepoel

title KIRO_MCP Dashboard Server

echo.
echo ========================================
echo   KIRO_MCP Dashboard Server
echo ========================================
echo.
echo Starting dashboard server...
echo.
echo Dashboard will be available at:
echo   http://localhost:5000
echo.
echo Opening dashboard in browser...
echo.

REM Start the Flask server
start /B python mcp_dashboard_server.py

REM Wait 2 seconds for server to start
timeout /t 2 /nobreak >nul

REM Open the HTML dashboard in default browser
start mcp_monitor_dashboard.html

echo.
echo Dashboard is now running!
echo Press Ctrl+C to stop the server.
echo.

REM Keep the window open
pause
