@echo off
rem Runs the review version on this computer only, at http://localhost:8542
cd /d "%~dp0"
py -3.15 -m streamlit run ND_BIW\dashboard\app.py --server.port 8542 --browser.gatherUsageStats false
