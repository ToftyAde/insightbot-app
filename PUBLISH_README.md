# Publish Pipeline (One Command)

### Install once (from project root, inside your venv)
```
pip install requests pyyaml beautifulsoup4 lxml
```

### Run pipeline
```
python scripts/publish.py
```
Or via batch:
```
windows_pipeline.bat
```

This will:
1) Ingest (respect robots.txt) → `data/raw/seed/*.html` + `_manifest.csv`
2) Preprocess HTML → `data/interim/seed/*.jsonl`
3) Extract & publish → `data/processed/latest/articles.csv`
