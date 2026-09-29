@echo off
cd /d "%~dp0"
py -3 BooruGet.py --gui
if errorlevel 1 pause
