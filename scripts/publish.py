#!/usr/bin/env python
"""
publish.py — One-command pipeline for InsightBot

Runs (in order):
  0) ingest_rss.py        (pulls up to 8 items per source via RSS/Atom)
  1) [optional] HTML pipeline:
       ingest_urls.py  (robots-aware)
       preprocess_html.py
       extract_content.py  → articles_html.csv

Finally merges (dedup by URL, newest first):
  data/processed/latest/articles_rss.csv
  data/processed/latest/articles_html.csv
→ writes:
  data/processed/latest/articles.csv

Usage (from project root):
  # Fast default (RSS only)
  python scripts/publish.py --verbose

  # Include HTML pipeline (slower; some sites block via robots)
  python scripts/publish.py --with-html --verbose

Options:
  --config PATH           YAML for both RSS & HTML (default: configs/sources_train.yaml)
  --rss-config PATH       YAML specifically for RSS (default: same as --config)
  --out-raw PATH          Raw HTML output folder (default: data/raw/seed)
  --timeout SECONDS       Request timeout (default: 12)
  --delay SECONDS         Base delay between requests (default: 2.0)
  --ignore-robots         Ignore robots.txt (NOT recommended)
  --with-html             Enable HTML pipeline (ingest + preprocess + extract)
  --skip-rss              Skip RSS step
  --merge-only            Skip all steps and only do final merge of existing CSVs
  --verbose               Stream subprocess logs live
"""
import argparse, os, sys, subprocess, time
from pathlib import Path
import pandas as pd  # needed for final merge

DEFAULT_CONFIG = "configs/sources_train.yaml"
DEFAULT_OUT_RAW = "data/raw/seed"

def run_step(cmd, verbose=False):
    print(">", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = []
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            lines.append(line)
            if verbose:
                print(line, end="")
    rc = proc.wait()
    return rc, "".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--rss-config", default=None)
    ap.add_argument("--out-raw", default=DEFAULT_OUT_RAW)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--with-html", action="store_true")
    ap.add_argument("--skip-rss", action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    project_root = Path.cwd()
    scripts_dir  = project_root / "scripts"
    data_dir     = project_root / "data"
    latest_dir   = data_dir / "processed" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    ingest_rss_py   = scripts_dir / "ingest_rss.py"
    ingest_html_py  = scripts_dir / "ingest_urls.py"
    preprocess_py   = scripts_dir / "preprocess_html.py"
    extract_py      = scripts_dir / "extract_content.py"

    # CSV paths
    rss_csv   = latest_dir / "articles_rss.csv"
    html_csv  = latest_dir / "articles_html.csv"
    final_csv = latest_dir / "articles.csv"

    rss_cfg = args.rss_config or args.config

    # If we're going to run HTML later, check those scripts exist
    with_html = args.with_html
    if with_html and not args.merge_only:
        for p in (preprocess_py, extract_py):
            if not p.exists():
                print(f"ERROR: Missing script: {p}")
                sys.exit(2)

    start = time.time()
    print("=== InsightBot Publish Pipeline ===")

    # 0) RSS ingest (fast, reliable)
    if not args.skip_rss and not args.merge_only:
        if not ingest_rss_py.exists():
            print(f"WARNING: {ingest_rss_py} not found — skipping RSS step.")
        else:
            cmd = [sys.executable, str(ingest_rss_py), "--config", rss_cfg, "--out", str(rss_csv)]
            rc, _ = run_step(cmd, verbose=args.verbose)
            if rc != 0:
                print(f"RSS step returned non-zero exit code: {rc}")
            else:
                print(f"RSS step completed (wrote rss csv? {'yes' if rss_csv.exists() else 'no'}).")

    # 1–3) HTML pipeline (only if explicitly enabled)
    if with_html and not args.merge_only:
        if not ingest_html_py.exists():
            print(f"WARNING: Missing ingest script at {ingest_html_py}; skipping HTML ingest step.")
        else:
            cmd = [
                sys.executable, str(ingest_html_py),
                "--config", args.config,
                "--out", args.out_raw,
                "--timeout", str(args.timeout),
                "--delay", str(args.delay)
            ]
            if args.ignore_robots:
                cmd.append("--ignore-robots")
            rc, _ = run_step(cmd, verbose=args.verbose)
            if rc != 0:
                print("Ingest (HTML) step returned non-zero exit code:", rc)
            else:
                print("Ingest (HTML) step completed.")

        # Preprocess (HTML)
        rc, _ = run_step([sys.executable, str(preprocess_py)], verbose=args.verbose)
        if rc != 0:
            print("Preprocess step failed:", rc)
            sys.exit(rc)
        print("Preprocess step completed.")

        # Extract (HTML) — try to write directly to articles_html.csv; fallback to rename
        html_before = set(latest_dir.glob("*.csv"))
        rc, _ = run_step([sys.executable, str(extract_py), "--out", str(html_csv)], verbose=args.verbose)
        if rc != 0:
            print("Extract step returned non-zero exit (maybe no --out support); trying fallback…")
            rc2, _ = run_step([sys.executable, str(extract_py)], verbose=args.verbose)
            if rc2 != 0:
                print("Extract step failed:", rc2)
                sys.exit(rc2)

        produced = None
        if html_csv.exists():
            produced = html_csv
        else:
            html_after = set(latest_dir.glob("*.csv"))
            new_files = list(html_after - html_before)
            cand = [p for p in new_files if p.name == "articles.csv"]
            produced = cand[0] if cand else (sorted(new_files, key=lambda p: p.stat().st_mtime, reverse=True)[0] if new_files else None)
            if produced:
                try:
                    produced.replace(html_csv)
                except Exception:
                    import shutil
                    shutil.copyfile(produced, html_csv)

        if not html_csv.exists():
            print("WARNING: HTML extract did not produce a CSV we could find.")
        else:
            print(f"Extract step completed. HTML CSV → {html_csv}")

    # Final merge (can be run standalone with --merge-only)
    frames = []
    if rss_csv.exists():
        try:
            frames.append(pd.read_csv(rss_csv))
        except Exception as e:
            print(f"WARNING: failed reading {rss_csv}: {e}")
    if html_csv.exists():
        try:
            frames.append(pd.read_csv(html_csv))
        except Exception as e:
            print(f"WARNING: failed reading {html_csv}: {e}")

    if frames:
        df = pd.concat(frames, ignore_index=True)
        keep_cols = ["title", "body", "language", "date", "source", "url"]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = ""
        df = df[keep_cols].drop_duplicates(subset=["url"])
        try:
            df = df.sort_values("date", ascending=False)
        except Exception:
            pass
        df.to_csv(final_csv, index=False, encoding="utf-8")
        print(f"Merged {sum(len(x) for x in frames)} rows → {len(df)} unique → {final_csv}")
    else:
        print("No new CSVs to merge. (Check earlier warnings.)")

    dur = time.time() - start
    print(f"Done. Total time: {dur:.1f}s")

if __name__ == "__main__":
    main()
