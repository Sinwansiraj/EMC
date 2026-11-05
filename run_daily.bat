@echo off
REM Daily job-agent run. Schedule with Windows Task Scheduler (see README).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m job_agent run --no-interactive >> private\daily_run.log 2>&1
python -m job_agent report > private\latest_report.txt
