@echo off
rem Runs the review version on this computer only, at http://localhost:8542 (no review password needed here)
cd /d "%~dp0"
set ND_BIW_REVIEW_LOCAL=1
py -3.15 -m streamlit run ND_BIW\dashboard\app.py --server.port 8542 --browser.gatherUsageStats false
