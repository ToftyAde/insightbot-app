#!/usr/bin/env python
"""
Minimal ingestion: fetch one HTML page per source (usually the homepage)
and save it under data/raw/seed/. Respects robots.txt by default.

Usage (from project root):
  python scripts/ingest_urls.py --config configs/sources_train.yaml --out data/raw/seed

Options:
  --ignore-robots    Ignore robots.txt (NOT recommended)
  --timeout 10       Per-request timeout seconds (default 12)
  --delay 2.0        Base delay seconds between requests (default 2.0)
"""
import argparse, os, sys, csv, time, random, json, pathlib, datetime
from urllib.parse import urlparse
from urllib import robotparser

try:
    import yaml  # PyYAML
except Exception:
    print("Missing dependency: pyyaml. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import requests
except Exception:
    print("Missing dependency: requests. Install with: pip install requests")
    sys.exit(1)

USER_AGENT = "InsightBotCrawler/0.1 (+https://example.com; contact=admin@example.com)"

def load_sources(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    items = cfg.get("sources", [])
    # Normalize
    out = []
    for it in items:
        out.append({
            "name": it.get("name", ""),
            "url": it.get("url", ""),
            "language": it.get("language", ""),
            "group": it.get("group", ""),
        })
    return out

def robots_allows(url, user_agent=USER_AGENT, ignore=False):
    if ignore:
        return True
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robots cannot be fetched, fail closed (disallow) to be safe.
        return False

def safe_filename(url):
    netloc = urlparse(url).netloc.replace(":", "_")
    if not netloc:
        netloc = "unknown"
    return netloc + ".html"

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def write_manifest_row(man_csv, row):
    header = ["name","url","language","group","status","http_status","path","timestamp","final_url"]
    new_file = not os.path.exists(man_csv)
    with open(man_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in header})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="YAML with sources[] list")
    ap.add_argument("--out", default="data/raw/seed", help="Output directory")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--ignore-robots", action="store_true")
    args = ap.parse_args()

    sources = load_sources(args.config)
    out_dir = args.out
    ensure_dir(out_dir)
    manifest_csv = os.path.join(out_dir, "_manifest.csv")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for i, s in enumerate(sources, 1):
        url = s["url"].strip()
        name = s["name"].strip() or url
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        row = {"name": name, "url": url, "language": s.get("language",""), "group": s.get("group",""), "timestamp": ts}

        if not url.startswith("http"):
            row.update({"status":"skip_invalid_url","http_status":"","path":"","final_url":""})
            write_manifest_row(manifest_csv, row)
            print(f"[{i}/{len(sources)}] SKIP invalid URL: {url}")
            continue

        if not robots_allows(url, ignore=args.ignore_robots):
            row.update({"status":"blocked_by_robots","http_status":"","path":"","final_url":""})
            write_manifest_row(manifest_csv, row)
            print(f"[{i}/{len(sources)}] BLOCKED by robots: {url}")
            continue

        fn = safe_filename(url)
        out_path = os.path.join(out_dir, fn)

        try:
            resp = session.get(url, timeout=args.timeout, allow_redirects=True)
            final_url = resp.url
            # Minimal HTML save
            with open(out_path, "wb") as f:
                f.write(resp.content)

            # Small sidecar meta
            meta = {
                "source": s,
                "requested_url": url,
                "final_url": final_url,
                "status_code": resp.status_code,
                "fetched_at": ts,
                "headers": {k: v for k, v in resp.headers.items()},
            }
            with open(out_path + ".meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            row.update({"status":"ok","http_status":str(resp.status_code),"path":out_path,"final_url":final_url})
            write_manifest_row(manifest_csv, row)
            print(f"[{i}/{len(sources)}] OK {name} -> {fn} ({resp.status_code})")

        except requests.RequestException as e:
            row.update({"status":"error","http_status":"","path":"","final_url":""})
            write_manifest_row(manifest_csv, row)
            print(f"[{i}/{len(sources)}] ERROR {name}: {e}")

        # Friendly randomized delay
        time.sleep(args.delay + random.uniform(0.0, 0.8))

    print("\nDone. See manifest:", manifest_csv)

if __name__ == "__main__":
    main()
