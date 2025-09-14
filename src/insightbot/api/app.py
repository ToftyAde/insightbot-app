# src/insightbot/api/app.py
import os, glob, logging
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from ..config import settings

# Load .env if present
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("insightbot.app")

# NOTE: adjust these paths if your app layout changes
app = Flask(__name__, template_folder="../../../templates", static_folder="../../../static")
app.secret_key = settings.SECRET_KEY

REQUIRED_COLS = ["title", "body", "language", "date", "source", "url"]
DEFAULT_LANG = settings.DEFAULT_LANGUAGE
FINAL_CSV = Path(settings.PROCESSED_DIR) / "articles.csv"  # expected merged output


# ---------- Template globals ----------
@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}


# ---------- Helpers ----------
def _best_last_updated(df: pd.DataFrame) -> str:
    """
    Choose the freshest timestamp between:
      - the max(df['date']) parsed as UTC
      - the file mtime of the final merged CSV
    Return a nicely formatted local-time string, or '—' if unknown.
    """
    chosen = None

    # 1) Try max(date) from data
    try:
        if not df.empty and "date" in df.columns:
            dts = pd.to_datetime(df["date"], errors="coerce", utc=True)
            if dts.notna().any():
                chosen = dts.max().to_pydatetime()
    except Exception:
        pass

    # 2) Fallback: file modified time
    try:
        if FINAL_CSV.exists():
            mtime = datetime.fromtimestamp(FINAL_CSV.stat().st_mtime, tz=timezone.utc)
            if (chosen is None) or (mtime > chosen):
                chosen = mtime
    except Exception:
        pass

    if not chosen:
        return "—"
    # Format in server's local timezone (change .astimezone() if you want a fixed TZ)
    return chosen.astimezone().strftime("%A %B %d, %Y @%I:%M%p")


# ---------- Data loading / filtering ----------
def load_articles():
    # Load ALL csvs under PROCESSED_DIR (rss/html) so pages can still render
    csv_paths = glob.glob(os.path.join(settings.PROCESSED_DIR, "*.csv"))
    frames = []
    for p in csv_paths:
        try:
            df = pd.read_csv(p)
            cols = [c for c in REQUIRED_COLS if c in df.columns]
            df = df[cols]
            for c in REQUIRED_COLS:
                if c not in df.columns:
                    df[c] = ""
            frames.append(df[REQUIRED_COLS])
        except Exception as e:
            log.warning(f"Failed to read {p}: {e}")
    if frames:
        out = pd.concat(frames, ignore_index=True).drop_duplicates()
        # keep dates as strings for template, parsing happens when needed
        if "date" in out.columns:
            out["date"] = out["date"].astype(str)
        return out
    return pd.DataFrame(columns=REQUIRED_COLS)


def filter_df(df, q=None, language=None, source=None):
    if df.empty:
        return df
    filtered = df.copy()
    if language and language.lower() != "all":
        filtered = filtered[filtered["language"].str.lower() == language.lower()]
    if source and source.lower() != "all":
        filtered = filtered[filtered["source"].str.contains(source, case=False, na=False)]
    if q:
        ql = q.lower()
        mask = (
            filtered["title"].str.lower().str.contains(ql, na=False) |
            filtered["body"].str.lower().str.contains(ql, na=False)
        )
        filtered = filtered[mask]
    return filtered


def apply_date_filter(df, date_key: str):
    """Filter df by date_key: '', 'today', '7d', '30d'. Best-effort parse."""
    if not df.empty and "date" in df.columns and date_key:
        try:
            now = datetime.now(timezone.utc)
            if date_key == "today":
                start = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_key.endswith("d") and date_key[:-1].isdigit():
                start = now - timedelta(days=int(date_key[:-1]))
            else:
                return df

            def _ok(d):
                s = str(d).strip()
                if not s:
                    return False
                # try robust parse with pandas
                dt = pd.to_datetime(s, errors="coerce", utc=True)
                if pd.isna(dt):
                    return False
                return dt.to_pydatetime(timezone.utc) >= start

            return df[df["date"].apply(_ok)]
        except Exception:
            return df
    return df


# ---------- Routes ----------
@app.route("/")
def landing():
    df = load_articles()

    # Language counts
    lang_counts = {}
    if not df.empty and "language" in df.columns:
        lang_counts = df["language"].fillna("").value_counts().to_dict()

    # Top sources (by frequency)
    sources_top = []
    if not df.empty and "source" in df.columns:
        vc = df["source"].fillna("").value_counts().head(30)
        for label, cnt in vc.items():
            sources_top.append({"label": label, "host": label, "count": int(cnt)})

    total_articles = int(len(df))
    last_updated = _best_last_updated(df)

    return render_template(
        "landing.html",
        lang_counts=lang_counts,
        sources_top=sources_top,
        total_articles=total_articles,
        sources_count=len(sources_top),
        last_updated=last_updated
    )


@app.route("/articles")
def articles():
    q = request.args.get("q", "").strip()
    language = request.args.get("language", "All").strip() or "All"
    source = request.args.get("source", "All").strip() or "All"
    date_key = request.args.get("date", "").strip()  # "", "today", "7d", "30d"

    df = load_articles()
    df = apply_date_filter(df, date_key)
    filtered = filter_df(df, q=q, language=language, source=source)

    # Simple facets (from the filtered base set pre-pagination)
    languages = ["All"] + sorted([l for l in df["language"].dropna().unique().tolist() if l])
    sources = ["All"] + sorted([s for s in df["source"].dropna().unique().tolist() if s])

    # Paginate
    page = int(request.args.get("page", "1"))
    per_page = 24
    start = (page - 1) * per_page
    end = start + per_page
    total = len(filtered)

    # Add a 'host' field for robust favicons
    items = filtered.iloc[start:end].to_dict(orient="records")
    for it in items:
        host = ""
        try:
            host = urlparse(it.get("url", "")).netloc or it.get("source", "")
        except Exception:
            host = it.get("source", "")
        it["host"] = host

    return render_template(
        "articles.html",
        q=q, language=language, source=source, date=date_key,
        languages=languages, sources=sources,
        items=items, total=total, page=page, per_page=per_page
    )


# ---------- Dashboards (Native charts; no Tableau) ----------
@app.route("/dashboards")
def dashboards():
    """Render the native charts page (Chart.js)."""
    return render_template("dashboards.html")


# ---------- Metrics API (for native charts) ----------
def _as_date(d):
    try:
        return pd.to_datetime(str(d), errors="coerce", utc=True).date()
    except Exception:
        return None

@app.route("/api/metrics/volume")
def api_metrics_volume():
    """
    Returns points [{date: 'YYYY-MM-DD', count: N}, ...]
    Query: ?date=today|7d|30d (optional)
    """
    date_key = request.args.get("date", "").strip()
    df = load_articles()
    df = apply_date_filter(df, date_key)

    if df.empty:
        return jsonify([])

    s = df["date"].apply(_as_date)
    g = s.value_counts().sort_index()
    data = [{"date": d.strftime("%Y-%m-%d"), "count": int(c)} for d, c in g.items() if pd.notna(d)]
    return jsonify(data)

@app.route("/api/metrics/languages")
def api_metrics_languages():
    """
    Returns [{label: 'English', count: N}, ...] sorted desc
    Query: ?date=...
    """
    date_key = request.args.get("date", "").strip()
    df = load_articles()
    df = apply_date_filter(df, date_key)

    if df.empty or "language" not in df.columns:
        return jsonify([])

    vc = df["language"].fillna("").replace("", "Unknown").value_counts()
    data = [{"label": str(k), "count": int(v)} for k, v in vc.items()]
    return jsonify(data)

@app.route("/api/metrics/sources")
def api_metrics_sources():
    """
    Returns top sources [{label: 'bbc.com', count: N}, ...]
    Query: ?top=15 (default 15), ?date=...
    """
    top_n = max(1, int(request.args.get("top", "15") or 15))
    date_key = request.args.get("date", "").strip()
    df = load_articles()
    df = apply_date_filter(df, date_key)

    if df.empty or "source" not in df.columns:
        return jsonify([])

    vc = df["source"].fillna("").replace("", "Unknown").value_counts().head(top_n)
    data = [{"label": str(k), "count": int(v)} for k, v in vc.items()]
    return jsonify(data)


@app.route("/export.csv")
def export_csv():
    q = request.args.get("q", "").strip()
    language = request.args.get("language", "").strip() or None
    source = request.args.get("source", "").strip() or None
    date_key = request.args.get("date", "").strip()

    df = load_articles()
    df = apply_date_filter(df, date_key)
    df = filter_df(df, q=q, language=language, source=source)

    csv_data = df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=articles_export.csv"}
    )


@app.route("/api/articles")
def api_articles():
    q = request.args.get("q", "").strip()
    language = request.args.get("language", "").strip()
    source = request.args.get("source", "").strip()
    date_key = request.args.get("date", "").strip()

    df = load_articles()
    df = apply_date_filter(df, date_key)
    filtered = filter_df(df, q=q, language=language or None, source=source or None)
    return jsonify(filtered.to_dict(orient="records"))


@app.route("/health")
def health():
    return jsonify(
        status="ok",
        processed_dir=settings.PROCESSED_DIR,
        total=len(load_articles())
    )


if __name__ == "__main__":
    port = settings.PORT
    log.info(f"Processed dir: {settings.PROCESSED_DIR}")
    app.run(host="0.0.0.0", port=port, debug=True)
