@echo off
rem One-click launcher: serve this folder and open the practice page.
cd /d "%~dp0"
echo Starting local server at http://localhost:8000 ...
start "" /min cmd /c "python -m http.server 8000"
timeout /t 2 >nul
start "" "http://localhost:8000/practice.html"
echo.
echo Practice page opened in your browser.
echo Close the minimized console window when you are done.
timeout /t 5 >nul
