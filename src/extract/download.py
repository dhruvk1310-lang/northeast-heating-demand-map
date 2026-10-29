"""Download helper with caching and retries."""

import re
import time
from pathlib import Path

import requests

from src.config import NOAA_CLIMDIV, RAW, RAW_FILES, URLS

HEADERS = {"User-Agent": "northeast-heating-demand-map (portfolio project; Python requests)"}


def download(url: str, dest: Path, force: bool = False, retries: int = 3) -> Path:
    """Save url to dest, skipping the download if dest already exists."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"  cached  {dest.relative_to(RAW.parent.parent)}")
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            tmp.rename(dest)
            mb = dest.stat().st_size / 1e6
            print(f"  fetched {dest.relative_to(RAW.parent.parent)} ({mb:.1f} MB)")
            return dest
        except requests.RequestException as e:
            if attempt == retries:
                raise
            wait = 5 * attempt
            print(f"  retry {attempt}/{retries - 1} after error: {e} (waiting {wait}s)")
            time.sleep(wait)
    return dest


def fetch(key: str, force: bool = False) -> Path:
    """Download one of the sources listed in config.URLS and return its path."""
    return download(URLS[key], RAW / RAW_FILES[key], force=force)


def latest_climdiv_file(element: str) -> str:
    """Return the newest NOAA climdiv file name for an element, e.g. 'hddccy'.

    NOAA renames these files with a date stamp each month, so the name is
    looked up from the directory listing instead of being hard-coded.
    """
    html = requests.get(NOAA_CLIMDIV, headers=HEADERS, timeout=60).text
    names = sorted(set(re.findall(rf"climdiv-{element}-v[\d.]+-\d{{8}}", html)))
    if not names:
        raise RuntimeError(f"No climdiv file found for element {element!r}")
    return names[-1]
