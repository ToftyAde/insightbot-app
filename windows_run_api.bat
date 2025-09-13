@echo off
call .venv\Scripts\activate
set FLASK_APP=src/insightbot/api/app.py
python src\insightbot\api\app.py
