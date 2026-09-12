"""
Script to fetch real-time Two-Line Element (TLE) satellite and space debris data
from CelesTrak and save to data/raw/.
"""

import os
import sys
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TLE_Fetcher")

DATA_DIR = os.getenv("DATA_DIR", "data/raw")

FEEDS = {
    "active_satellites.tle": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
    "stations.tle": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    "geo_satellites.tle": "https://celestrak.org/NORAD/elements/gp.php?GROUP=geo&FORMAT=tle"
}

def download_tles():
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.info(f"Target directory for TLEs: {os.path.abspath(DATA_DIR)}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Clean up stale files if invalid
    for fname in ["debris_catalog.tle"]:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            os.remove(fpath)

    for filename, url in FEEDS.items():
        filepath = os.path.join(DATA_DIR, filename)
        logger.info(f"Fetching live TLE feed from: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            lines = [line for line in response.text.strip().split('\n') if line.strip()]
            
            # Ensure file starts with valid TLE line
            if len(lines) >= 2 and (lines[0].startswith('1 ') or len(lines[0]) > 20):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                logger.info(f"✅ Saved {len(lines)} TLE lines to: {filepath}")
            else:
                logger.warning(f"⚠️ Response from {url} did not contain valid TLE format")

        except Exception as e:
            logger.error(f"❌ Failed to fetch {filename} from {url}: {e}")

if __name__ == "__main__":
    download_tles()
