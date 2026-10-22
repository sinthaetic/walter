@echo off
rem Dubbelklicka for att se Walters forslag och godkanna det (paper, inga riktiga pengar).
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (.venv\Scripts\python.exe fetcher\walter_paper.py) else (python fetcher\walter_paper.py)
pause
