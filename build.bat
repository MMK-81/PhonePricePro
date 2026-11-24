@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Building PhonePricePro portable...
python -m PyInstaller --noconfirm --clean PhonePricePro.spec
if errorlevel 1 (
  echo BUILD FAILED
  pause
  exit /b 1
)
echo Portable build ready in dist\PhonePricePro
pause
