#!/usr/bin/env python
import os, sys, json, hashlib, logging, argparse
from datetime import datetime, timezone
from urllib.parse import urljoin
import pandas as pd

# deps
import yaml, feedparser
from dateutil import parser as dp

# for RSS auto-discovery and prefetch
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("insightbot.rss")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

N_PER_SOURCE  = 8
DEFAULT_LANG  = "English"
OUT_DEFAULT   = os.path.join("data", "processed", "latest", "articles_rss.csv")
USER_AGENT    = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InsightBotScraper/1.0 (+https://github.com/ToftyAde/insightbot-app)"

def url_hash(u: str) -> str:
    return hashlib.sha256((u or "").strip().lower().encode()).hexdigest()

def load_sources(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # expect: sources: [ {name, url, language, [optional] rss } ]
    return cfg.get("sources", [])

def html_to_text(html: str, max_len: int = 800) -> str:
    """Strip tags to text, collapse whitespace, and trim."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = " ".join(s.strip() for s in soup.stripped_strings)
    return (text[:max_len] + "…") if len(text) > max_len else text

def autodiscover_rss(home_url: str) -> str | None:
    """Try to find an RSS/Atom feed from a homepage."""
    try:
        r = requests.get(home_url, timeout=20, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # common link rels
        for link in soup.find_all("link", rel=lambda v: v and "alternate" in v):
            typ = (link.get("type") or "").lower()
            if "rss" in typ or "atom" in typ or "xml" in typ:
                href = link.get("href")
                if not href:
                    continue
                return urljoin(home_url, href)
    except Exception as e:
        log.debug(f"autodiscover failed for {home_url}: {e}")
    return None

def parse_date(val):
    if not val:
        return None
    try:
        return dp.parse(val).astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def parse_feed(rss_url: str):
    """Fetch feed with UA first (to avoid 403/empty), then parse."""
    try:
        r = requests.get(rss_url, timeout=20, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return feedparser.parse(r.text)
    except Exception:
        return feedparser.parse(rss_url)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="YAML with sources[] (url + optional rss)")
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    rows, seen = [], set()

    for src in load_sources(args.config):
        name = (src.get("name") or src.get("url") or "source").strip()
        lang = src.get("language") or DEFAULT_LANG

        rss = src.get("rss")
        if not rss:
            base_url = src.get("url")
            if not base_url:
                log.warning(f"{name}: no url provided; skipping")
                continue
            rss = autodiscover_rss(base_url)
            if not rss:
                log.info(f"{name}: no rss found; skipping")
                continue

        d = parse_feed(rss)
        if not getattr(d, "entries", None):
            log.info(f"{name}: feed empty or unreadable; skipping")
            continue

        items = []
        for e in d.entries:
            title_raw = getattr(e, "title", "") or ""
            link      = getattr(e, "link", "") or ""
            if not link:
                continue
            summary_raw = getattr(e, "summary", "") or getattr(e, "description", "") or ""
            pub        = getattr(e, "published", "") or getattr(e, "updated", "") or ""
            date_iso   = parse_date(pub) or datetime.now(timezone.utc).isoformat()

            items.append({
                "title":    html_to_text(title_raw,   max_len=180).strip(),
                "body":     html_to_text(summary_raw, max_len=800).strip(),
                "language": lang,
                "date":     date_iso,
                "source":   name,
                "url":      link.strip(),
            })

        # newest first, cap N_PER_SOURCE and dedupe by URL
        items.sort(key=lambda r: r["date"], reverse=True)
        kept = 0
        for it in items:
            if kept >= N_PER_SOURCE:
                break
            h = url_hash(it["url"])
            if h in seen:
                continue
            seen.add(h)
            kept += 1
            rows.append(it)

        log.info(f"{name}: kept {kept} items")

    # write CSV (even if empty)
    df = pd.DataFrame(rows, columns=["title", "body", "language", "date", "source", "url"])
    if not df.empty:
        df = df.drop_duplicates(subset=["url"]).sort_values("date", ascending=False)
    df.to_csv(args.out, index=False, encoding="utf-8")
    log.info(f"Wrote {len(df)} rows → {args.out}")

if __name__ == "__main__":
    main()
