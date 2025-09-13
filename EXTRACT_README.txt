## Preprocess & Extract
1) Install extra deps:
```
pip install beautifulsoup4 lxml
```
2) Preprocess (convert HTML -> interim JSONL blocks):
```
python scripts/preprocess_html.py
```
3) Extract (pick best block, write processed/latest/articles.csv):
```
python scripts/extract_content.py
```
4) Start the app and open /articles:
```
python -m insightbot.api.app
```
