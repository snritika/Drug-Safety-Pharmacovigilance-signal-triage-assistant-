"""Download and unzip FAERS quarterly ASCII extracts. Stdlib only."""
import io
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

BASE_URL = "https://fis.fda.gov/content/Exports"  # verify in your browser first
DEST = Path("data/faers")
QUARTERS = [f"{y}q{q}" for y in range(2021, 2027) for q in range(1, 5)]
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; pharmacovigilance portfolio)"}


def fetch(quarter: str) -> None:
    target = DEST / quarter
    if target.exists() and any(target.iterdir()):
        print(f"skip {quarter}: already present")
        return
    url = f"{BASE_URL}/faers_ascii_{quarter}.zip"
    print(f"download {quarter} ...", flush=True)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = resp.read()
    except Exception as exc:  # 404 for quarters not yet published, etc.
        print(f"  failed {quarter}: {exc}", file=sys.stderr)
        return
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(target)
    print(f"  unzipped to {target}")
    time.sleep(2)  # be polite to the server


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    for q in QUARTERS:
        fetch(q)