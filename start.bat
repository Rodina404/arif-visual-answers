@echo off
rem Arif Visual Answers: one-click start for Windows.
rem Installs what the app needs (first run only), builds the web page, starts the server
rem on http://localhost:8000 and opens it in the browser. Close this window to stop Arif.
setlocal
cd /d "%~dp0"
title Arif Visual Answers
set "PATH=%PATH%;%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\nodejs;%APPDATA%\Python\Python313\Scripts"
set PYTHONUTF8=1

where uv >nul 2>nul
if errorlevel 1 (
  echo [!] "uv" is not installed. See step 2 of the guide: docs\Arif-Visual-Answers-Guide.pdf
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [!] Node.js is not installed. See step 2 of the guide: docs\Arif-Visual-Answers-Guide.pdf
  pause
  exit /b 1
)

if not exist .env (
  copy .env.example .env >nul
  echo Created the settings file .env
)

rem Live mode when .env has an API key, otherwise the offline demo (recorded answers).
set MOCK_LLM=1
findstr /r /c:"^GROQ_API_KEY=[^ #]" /c:"^GEMINI_API_KEY=[^ #]" .env >nul
if not errorlevel 1 set MOCK_LLM=0

echo.
echo [1/3] Installing the server part (the first run takes a few minutes)...
pushd backend
uv sync
if errorlevel 1 goto fail
popd

echo.
echo [2/3] Building the web page...
pushd frontend
if not exist node_modules (
  call npm ci
  if errorlevel 1 goto fail
)
call npm run build
if errorlevel 1 goto fail
popd

echo.
if "%MOCK_LLM%"=="1" (
  echo [3/3] Starting Arif in OFFLINE DEMO mode: no API key in .env.
  echo       Real answers only for the sample PDFs in fixtures\pdfs. Add a key for your own PDFs.
) else (
  echo [3/3] Starting Arif in LIVE mode with the API key from .env.
)
echo       Arif opens in your browser at http://localhost:8000
echo       Keep this window open while you use Arif. Close it to stop.
echo.
start "" /b powershell -NoProfile -Command "for ($i=0; $i -lt 90; $i++) { try { Invoke-WebRequest -UseBasicParsing http://localhost:8000/healthz -TimeoutSec 2 | Out-Null; Start-Process 'http://localhost:8000'; break } catch { Start-Sleep -Seconds 1 } }"
cd backend
uv run uvicorn app.main:app --port 8000
echo.
echo Arif stopped. If you saw an error above, see "If something goes wrong" in the guide.
pause
exit /b 0

:fail
echo.
echo [!] Something went wrong above. See "If something goes wrong" in the guide.
pause
exit /b 1
