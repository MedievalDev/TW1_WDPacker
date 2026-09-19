@echo off
rem Startet die gebaute Exe im Selbsttest-Modus und zeigt die Zeile (PY_TOOL_DESIGN.md 7.6).
set "WD_PACKER_SELFTEST=%TEMP%\wd_packer_selftest.txt"
del "%WD_PACKER_SELFTEST%" 2>nul
start "" /wait "%~dp0dist\TW1_WD_Packer.exe"
timeout /t 3 >nul
type "%WD_PACKER_SELFTEST%"
