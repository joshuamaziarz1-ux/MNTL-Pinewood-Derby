@echo off
setlocal
cd /d %~dp0

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found.
  echo Install Python 3.12 or use the GitHub Actions build instead.
  pause
  exit /b 1
)

if not exist .venv (
  py -3.12 -m venv .venv
  if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 exit /b 1

python -m py_compile launcher.py app.py storage.py backup.py race_engine.py migration.py
if errorlevel 1 exit /b 1

pytest -q
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --onefile --windowed --name MNLT_Derby_Manager_v43 launcher.py
if errorlevel 1 exit /b 1

echo.
echo BUILD COMPLETE
echo EXE: %CD%\dist\MNLT_Derby_Manager_v43.exe
pause
