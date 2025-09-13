@echo off
REM Create venv and install dependencies
python -m venv .venv
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Setup complete. Run windows_run_api.bat to start the server.
