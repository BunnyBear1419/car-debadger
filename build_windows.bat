@echo off
setlocal
cd /d "%~dp0"

py -3 -m venv .venv
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error
pyinstaller --noconfirm --clean --windowed --name Car-Debadger --collect-all PySide6 main.py
if errorlevel 1 goto :error

echo.
echo Portable application created in dist\Car-Debadger\
echo To build the installer, install Inno Setup 6 and run:
echo ISCC.exe installer\Car-Debadger.iss
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Review the error above.
pause
exit /b 1
