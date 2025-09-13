# InsightBot Starter (Flask)

A minimal, production-ready starter aligned with your SRS. Reads processed CSV files from `data/processed/latest` and serves a clean UI.

## Quickstart (Windows)
1) Create venv & install deps:
```
windows_setup.bat
```
2) Create `.env` from example if you want overrides.
3) Run the app:
```
windows_run_api.bat
```
4) Open http://localhost:5001

## Data
Drop one or more CSV files with these columns in `data/processed/latest/`:
`title, body, language, date, source, url`

If no CSVs are present, the app still runs and shows an empty state.

## Structure
```
src/insightbot/api/app.py   # Flask app
templates/                  # Jinja templates
static/                     # CSS/JS/Images
configs/                    # App settings
scripts/                    # Helper scripts
data/processed/latest/      # Your processed CSVs
```
