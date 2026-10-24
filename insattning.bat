@echo off
rem Dubbelklicka for att satta in pengar i Walter (paper, inga riktiga pengar). Walter koper direkt.
rem Kor sedan "walter deploy" sa att Walter i GitHub och sidan ser insattningen.
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (.venv\Scripts\python.exe fetcher\walter_paper.py --insattning) else (python fetcher\walter_paper.py --insattning)
pause
