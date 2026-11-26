@echo off
rem Runs the review version on this computer only, at http://localhost:8542 (no review password needed here).
rem It listens on 127.0.0.1 only: with the password off, nobody else on the network may reach it.
cd /d "%~dp0"
set ND_BIW_REVIEW_LOCAL=1
"%USERPROFILE%\.venvs\nd-biw\Scripts\python.exe" -m streamlit run ND_BIW\dashboard\app.py --server.address 127.0.0.1 --server.port 8542 --browser.gatherUsageStats false
