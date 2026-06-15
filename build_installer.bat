@echo off
rem ============================================
rem AudioA — Build installer for Windows
rem Requires: Python 3, PyInstaller, Inno Setup
rem ============================================
setlocal

echo === 1/4: Generating icon...
python resources\generate_icon.py
if %errorlevel% neq 0 (
    echo ERROR: Failed to generate icon
    pause
    exit /b 1
)

echo === 2/4: Installing Python dependencies...
pip install pyside6 sounddevice pyinstaller
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo === 3/4: Building AudioA.exe with PyInstaller...
pyinstaller --onefile --windowed --name "AudioA" --add-data "resources/icon.png;resources" --icon resources\icon.ico audio_app.py
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed
    pause
    exit /b 1
)

echo === 4/4: Building installer with Inno Setup...
rem Adjust ISCC path if Inno Setup is installed elsewhere
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo WARNING: Inno Setup not found at %ISCC%
    echo Skipping installer build. The .exe is at dist\AudioA.exe
    pause
    exit /b 0
)

%ISCC% installer.iss
if %errorlevel% neq 0 (
    echo ERROR: Inno Setup build failed
    pause
    exit /b 1
)

echo === Done! Installer created: dist\AudioA_Setup.exe
pause
