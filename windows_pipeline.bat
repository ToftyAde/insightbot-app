@echo off
REM windows_pipeline.bat — run full publish pipeline
call .venv\Scripts\activate
python scripts\publish.py --config configs\sources_train.yaml --out-raw data\raw\seed --delay 2
