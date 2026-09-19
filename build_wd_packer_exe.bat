@echo off
rem Baut den TW1 WD Packer als eine Exe (PyInstaller, onefile, ohne Konsole).
rem Ergebnis: %~dp0dist\TW1_WD_Packer.exe
setlocal
pushd "%~dp0"
py -3.13 -m PyInstaller --noconfirm --onefile --windowed ^
  --name "TW1_WD_Packer" --icon "%~dp0wd_packer.ico" ^
  --add-data "%~dp0wd_packer.ico;." --add-data "%~dp0untested.json;." ^
  --hidden-import theme --hidden-import guidebook --hidden-import updater --hidden-import version ^
  --hidden-import wdcore --hidden-import wdio --hidden-import dropfiles ^
  --hidden-import foxfeedback --hidden-import foxfeedback_ui ^
  --distpath "%~dp0dist" --workpath "%TEMP%\wd_packer_build" --specpath "%TEMP%\wd_packer_build" wd_packer.py
set rc=%errorlevel%
popd
if %rc% neq 0 (echo BUILD FEHLGESCHLAGEN & exit /b %rc%)
echo BUILD OK: %~dp0dist\TW1_WD_Packer.exe
