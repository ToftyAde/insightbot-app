## Ingestion (seed pages)
Install additions:
```
pip install requests pyyaml
```
Run (from project root):
```
python scripts/ingest_urls.py --config configs/sources_train.yaml --out data/raw/seed
```
This will create `data/raw/seed/DOMAIN.html` (+ `.meta.json`) and a `_manifest.csv`.
It respects `robots.txt` by default; use `--ignore-robots` to override (not recommended).
