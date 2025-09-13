#!/usr/bin/env python
"""
Extract content: read data/interim/seed/*.jsonl and produce data/processed/latest/articles.csv
Heuristics:
- title: meta.title_guess or first line of best block
- body: best block by (p_count, length)
- date: from meta tags in original HTML's sidecar .meta.json if present
"""
import os, sys, json, csv, glob, pathlib, re
from datetime import datetime
from bs4 import BeautifulSoup

REQUIRED_COLS = ["title", "body", "language", "date", "source", "url"]

def read_meta_for(html_path):
    meta_path = html_path + ".meta.json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def pick_best_block(records):
    # records: list of {"meta":{}, "block":{selector,length,p_count,text}}
    if not records:
        return None
    rec = sorted(records, key=lambda r: (r["block"].get("p_count",0), r["block"].get("length",0)), reverse=True)[0]
    return rec

def find_date_in_html(html_path):
    # Try to parse publication time from original HTML
    try:
        with open(html_path, "rb") as f:
            soup = BeautifulSoup(f.read(), "lxml")
        # meta tags
        cands = [
            ("meta", {"property":"article:published_time"}, "content"),
            ("meta", {"name":"pubdate"}, "content"),
            ("meta", {"name":"date"}, "content"),
            ("time", {"datetime":True}, "datetime"),
        ]
        for tag, attrs, attr_name in cands:
            el = soup.find(tag, attrs=attrs)
            if el and el.has_attr(attr_name):
                return el.get(attr_name)
    except Exception:
        return ""
    return ""

def main():
    root = pathlib.Path(".")
    interim_dir = root / "data" / "interim" / "seed"
    raw_dir = root / "data" / "raw" / "seed"
    out_dir = root / "data" / "processed" / "latest"
    os.makedirs(out_dir, exist_ok=True)
    out_csv = out_dir / "articles.csv"

    rows = []
    for jf in sorted(interim_dir.glob("*.jsonl")):
        html_name = jf.name.replace(".jsonl", "")
        html_path = raw_dir / html_name
        meta = read_meta_for(str(html_path))

        # gather candidate blocks
        records = []
        with open(jf, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
        best = pick_best_block(records)
        if not best:
            continue

        title = best.get("meta",{}).get("title_guess") or ""
        if not title:
            text = best["block"].get("text","")
            # first sentence as fallback
            title = text.split(".")[0][:140].strip()

        body = best["block"].get("text","")[:2000]  # cap body

        # infer language lightly from domain or leave blank (user can adjust later)
        url = meta.get("final_url") or meta.get("requested_url") or ""
        source = ""
        if url:
            source = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]

        # date
        pub = find_date_in_html(str(html_path)) or meta.get("headers",{}).get("Last-Modified","")
        date = pub or ""

        # language guess by simple domain hint (very rough)
        language = ""
        if any(k in source for k in ["aljazeera","skynewsarabia","alarabiya","akhbaar","arabic.cnn","bbc.com"]):
            language = "Arabic"
        elif any(k in source for k in ["rbc.ru","rt.com","tass.com","meduza.io","echo.msk.ru","sputniknews"]):
            language = "Russian"
        else:
            language = "English"

        rows.append([title, body, language, date, source, url])

    # write CSV
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REQUIRED_COLS)
        for r in rows:
            w.writerow(r)
    print(f"Wrote {out_csv} with {len(rows)} rows")

if __name__ == "__main__":
    main()
