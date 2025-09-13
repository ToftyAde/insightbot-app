@echo off
REM Seed-ingest 40 training sites into data\raw\seed
call .venv\Scripts\activate
if not exist data\raw\seed mkdir data\raw\seed
python scripts\ingest_urls.py --config configs\sources_train.yaml --out data\raw\seed --delay 2
