@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
if not exist ".venv\installed.ok" (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto fail
  echo installed> .venv\installed.ok
)
.venv\Scripts\python.exe -m streamlit run app.py --server.address localhost --server.port 8501
if errorlevel 1 goto fail
exit /b 0
:fail
echo.
echo Setup or startup failed. Install Python 3.11 or newer from python.org with the Python launcher enabled.
echo If dependencies failed, check your internet connection and run this file again.
pause
exit /b 1
