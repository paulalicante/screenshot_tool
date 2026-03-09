@echo off
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

if exist "%APP_DIR%\.venv\Scripts\pythonw.exe" (
    start "" "%APP_DIR%\.venv\Scripts\pythonw.exe" "%APP_DIR%screenshot_tool_pyqt.py"
    exit /b 0
)

if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%APP_DIR%screenshot_tool_pyqt.py"
    exit /b 0
)

echo Python interpreter not found.
echo Expected: "%APP_DIR%\.venv\Scripts\pythonw.exe"
pause
