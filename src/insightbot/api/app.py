import os, glob, logging
from urllib.parse import urlparse
from datetime import datetime, timedelta

import pandas as pd
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from ..config import settings

# Load .env if present
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("insightbot.app")

app = Flask(__name__, template_folder="../../../templates", static_folder="../../../static")
app.secret_key = settings.SECRET_KEY

REQUIRED_COLS = ["title", "body", "language", "date", "source", "url"]
DEFAULT_LANG = settings.DEFAULT_LANGUAGE


# --- Globals in templates (e.g., footer year) ---
@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}


# --- Data loader ---
def load_articles():
    csv_paths = glob.glob(os.path.join(settings.PROCESSED_DIR, "*.csv"))
    frames = []
    for p in csv_paths:
        try:
            df = pd.read_csv(p)
            # keep only required cols if present
            cols = [c for c in REQUIRED_COLS if c in df.columns]
            df = df[cols]
            # ensure all required exist (fill missing)
            for c in REQUIRED_COLS:
                if c not in df.columns:
                    df[c] = ""
            frames.append(df[REQUIRED_COLS])
        except Exception as e:
            log.warning(f"Failed to read {p}: {e}")
    if frames:
        out = pd.concat(frames, ignore_index=True).drop_duplicates()
        # Normalize date to string for display
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
    if not date_key or df.empty or "date" not in df.columns:
        return df
    try:
        now = datetime.utcnow()
        if date_key == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_key.endswith("d") and date_key[:-1].isdigit():
            start = now - timedelta(days=int(date_key[:-1]))
        else:
            return df

        def _ok(d):
            s = str(d).strip()
            if not s:
                return False
            try:
                # tolerate trailing 'Z'
                return datetime.fromisoformat(s.replace("Z", "")).timestamp() >= start.timestamp()
            except Exception:
                # last resort: keep RFC-ish date via pandas to_datetime
                try:
                    return pd.to_datetime(s, errors="coerce").to_pydatetime() >= start
                except Exception:
                    return False

        return df[df["date"].apply(_ok)]
    except Exception:
        return df


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
            # We store host-ish value in 'source' already; use as both label & host
            sources_top.append({"label": label, "host": label, "count": int(cnt)})

    # Totals & last updated (best-effort)
    total_articles = int(len(df))
    last_updated = "—"
    if not df.empty and "date" in df.columns:
        try:
            last_updated = str(df["date"].dropna().max())
        except Exception:
            pass

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


if __name__ == "__main__":
    port = settings.PORT
    log.info(f"Processed dir: {settings.PROCESSED_DIR}")
    app.run(host="0.0.0.0", port=port, debug=True)
