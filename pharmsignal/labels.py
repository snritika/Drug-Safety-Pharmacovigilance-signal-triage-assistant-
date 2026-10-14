"""Fetch FDA drug labels from openFDA and cache each response on disk.

Each cached file records when it was fetched. The API key is sent in the
request but never written to the cache.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LABEL_URL = "https://api.fda.gov/drug/label.json"
API_KEY_ENV = "OPENFDA_API_KEY"
MAX_LABELS = 20
SECTIONS = (
      "warnings_and_cautions",
      "warnings",
      "adverse_reactions",
      "contraindications",
  )
Opener = Callable[[str], bytes]


def api_key_from_env() -> str | None:
    """Return the openFDA key from the environment, or None if it is not set."""
    key = os.environ.get(API_KEY_ENV, "").strip()
    return key or None


def build_url(drug: str, api_key: str | None = None) -> str:
    """Build a label search URL matching the generic or brand name exactly."""
    term = drug.strip().replace('"', "")
    search = f'(openfda.generic_name:"{term}" OR openfda.brand_name:"{term}")'
    params = {"search": search, "limit": str(MAX_LABELS)}
    if api_key:
        params["api_key"] = api_key
    return f"{LABEL_URL}?{urllib.parse.urlencode(params)}"


def cache_path(cache_dir: Path, drug: str) -> Path:
    """File path for one drug's cached label, e.g. 'Ibuprofen' -> ibuprofen.json."""
    slug = re.sub(r"[^a-z0-9]+", "_", drug.strip().lower()).strip("_")
    if not slug:
        raise ValueError("drug name is empty")
    return cache_dir / f"{slug}.json"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pharmsignal/0.1 (research)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_label(
    drug: str,
    cache_dir: Path,
    api_key: str | None = None,
    opener: Opener = _http_get,
    refresh: bool = False,
) -> dict:
    """Return the cached label record for a drug, fetching it if not cached.

    A record has keys: drug, fetched_at (UTC, ISO 8601), found (bool), response.
    openFDA answers 404 when nothing matches; that is cached as found=False.
    """
    path = cache_path(cache_dir, drug)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    url = build_url(drug, api_key)
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        body = json.loads(opener(url).decode("utf-8"))
        record = {"drug": drug, "fetched_at": fetched_at, "found": True, "response": body}
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        record = {"drug": drug, "fetched_at": fetched_at, "found": False, "response": None}

    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record