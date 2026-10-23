import io
import zipfile

import httpx

from app.config import settings


def client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.http_user_agent, "Accept": "*/*"},
        timeout=30,
        follow_redirects=True,
    )


def get_text(c: httpx.Client, url: str) -> str | None:
    """Fetch a CSV or zipped CSV. Returns None on 404 (e.g. market holiday)."""
    resp = c.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(zf.namelist()[0]).decode("utf-8", errors="replace")
    return resp.text
