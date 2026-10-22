@echo off
rem  walter visa dashboard  -> bygger om state.js (utan att hamta) och oppnar WALTER
rem  walter hamta           -> hamtar ny data och oppnar WALTER
rem  walter deploy          -> bygger sidan (marknad + krypterad owner.enc), kopierar till deploy\ och publicerar
rem                           WALTER_PAGES_REPO i fetcher\.env -> pushar gh-pages + state.enc till main
rem                           annars Netlify Drop. Se README_DEPLOY.md.
cd /d "%~dp0"
if /i "%~1 %~2"=="visa dashboard" goto visa
if /i "%~1"=="hamta" goto hamta
if /i "%~1"=="deploy" goto deploy
echo Anvand: walter visa dashboard  /  walter hamta  /  walter deploy
exit /b 1
:deploy
where git >nul 2>nul || echo OBS: git saknas - gh-pages kan inte pushas, Netlify Drop anvands.
.\.venv\Scripts\python.exe fetcher\walter_deploy.py
exit /b %errorlevel%
:hamta
.\.venv\Scripts\python.exe fetcher\walter_fetch.py
goto oppna
:visa
.\.venv\Scripts\python.exe fetcher\walter_fetch.py --offline
:oppna
start "" "%~dp0index.html"
