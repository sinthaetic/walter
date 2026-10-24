@echo off
rem Dubbelklicka for att satta in pengar i Walter (paper, inga riktiga pengar). Walter koper direkt.
rem Walter pushar den lasta state.enc till main direkt. Kor "walter deploy" for att se den pa sidan/mobilen.
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (.venv\Scripts\python.exe fetcher\walter_paper.py --insattning) else (python fetcher\walter_paper.py --insattning)
pause
