@echo off
rem Dubbelklicka för att hämta ny data till WALTER.
cd /d "%~dp0"
python fetcher\walter_fetch.py %*
pause
