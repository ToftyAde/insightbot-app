#!/usr/bin/env python
"""
publish.py — One-command pipeline for InsightBot

Runs:
  1) ingest_urls.py   (robots-aware)
  2) preprocess_html.py
  3) extract_content.py

Usage (from project root):
  python scripts/publish.py                          # uses defaults
  python scripts/publish.py --config configs/sources_train.yaml --out-raw data/raw/seed --delay 2

Options:
  --config PATH          YAML list of sources (default: configs/sources_train.yaml)
  --out-raw PATH         Raw HTML output folder (default: data/raw/seed)
  --timeout SECONDS      Request timeout (default: 12)
  --delay SECONDS        Base delay between requests (default: 2.0)
  --ignore-robots        Ignore robots.txt (NOT recommended)
  --skip-ingest          Skip ingest (run preprocess+extract only)
  --verbose              Print subprocess stdout live
"""
import argparse, os, sys, subprocess, shutil, time

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
    ap.add_argument("--out-raw", default=DEFAULT_OUT_RAW)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # Resolve project-relative paths
    project_root = os.getcwd()
    scripts_dir = os.path.join(project_root, "scripts")
    ingest_py = os.path.join(scripts_dir, "ingest_urls.py")
    preprocess_py = os.path.join(scripts_dir, "preprocess_html.py")
    extract_py = os.path.join(scripts_dir, "extract_content.py")

    for p in [preprocess_py, extract_py]:
        if not os.path.exists(p):
            print(f"ERROR: Missing script: {p}")
            sys.exit(2)

    start = time.time()
    print("=== InsightBot Publish Pipeline ===")

    # 1) Ingest
    if not args.skip_ingest:
        if not os.path.exists(ingest_py):
            print(f"WARNING: Missing ingest script at {ingest_py}; skipping ingest step.")
        else:
            cmd = ["python", ingest_py, "--config", args.config, "--out", args.out_raw, "--timeout", str(args.timeout), "--delay", str(args.delay)]
            if args.ignore_robots:
                cmd.append("--ignore-robots")
            rc, out = run_step(cmd, verbose=args.verbose)
            if rc != 0:
                print("Ingest step returned non-zero exit code:", rc)
            else:
                print("Ingest step completed.")

    # 2) Preprocess
    rc, out = run_step(["python", preprocess_py], verbose=args.verbose)
    if rc != 0:
        print("Preprocess step failed:", rc)
        sys.exit(rc)
    print("Preprocess step completed.")

    # 3) Extract
    rc, out = run_step(["python", extract_py], verbose=args.verbose)
    if rc != 0:
        print("Extract step failed:", rc)
        sys.exit(rc)
    print("Extract step completed.")

    dur = time.time() - start
    print(f"Done. Total time: {dur:.1f}s")
    print("Output CSV -> data/processed/latest/articles.csv")

if __name__ == "__main__":
    main()
