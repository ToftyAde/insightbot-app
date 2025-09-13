from urllib.parse import urlparse

def favicon_url(url: str) -> str:
    try:
        host = urlparse(url).netloc
        if not host:
            return "/static/img/fallback-favicon.svg"
        # Google S2 favicon (works without API keys)
        return f"https://www.google.com/s2/favicons?sz=32&domain={host}"
    except Exception:
        return "/static/img/fallback-favicon.svg"
