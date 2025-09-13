#!/usr/bin/env python
"""
Preprocess HTML: read data/raw/seed/*.html and write cleaned text blocks into data/interim/seed/*.jsonl
- Strips scripts/styles
- Records candidate blocks with basic scores (length, <p> count)
"""
import os, sys, json, glob, re, pathlib
from bs4 import BeautifulSoup

def clean_text(s):
    s = re.sub(r'\s+', ' ', s or '').strip()
    return s

def iter_candidate_blocks(soup):
    # Prefer <main>, <article>, then generic divs/sections
    selectors = [
        "main", "article", "[role='main']",
        "section", "div"
    ]
    for sel in selectors:
        for el in soup.select(sel):
            text = clean_text(el.get_text(" "))
            if not text: 
                continue
            p_count = len(el.find_all("p"))
            yield {
                "selector": sel,
                "length": len(text),
                "p_count": p_count,
                "text": text[:20000]  # cap per block
            }

def preprocess_one(html_path, out_path):
    with open(html_path, "rb") as f:
        raw = f.read()
    soup = BeautifulSoup(raw, "lxml")
    # Remove script/style
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Title guess
    title = None
    if soup.title and soup.title.string:
        title = clean_text(soup.title.string)
    h1 = soup.find("h1")
    if not title and h1:
        title = clean_text(h1.get_text(" "))

    # Collect blocks
    blocks = sorted(list(iter_candidate_blocks(soup)), key=lambda b: (b["p_count"], b["length"]), reverse=True)[:10]
    meta = {"title_guess": title}

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for b in blocks:
            rec = {"meta": meta, "block": b}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def main():
    root = pathlib.Path(".")
    src = root / "data" / "raw" / "seed"
    dst = root / "data" / "interim" / "seed"
    htmls = sorted(src.glob("*.html"))
    if not htmls:
        print("No HTML files in", src)
        sys.exit(0)
    for p in htmls:
        out = dst / (p.name + ".jsonl")
        preprocess_one(str(p), str(out))
        print("Wrote", out)
    print("Done.")
if __name__ == "__main__":
    main()
