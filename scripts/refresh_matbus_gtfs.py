from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campus_pathfinding.config import get_settings


def main() -> None:
    settings = get_settings()
    target_zip = settings.matbus_gtfs_zip_path
    target_dir = settings.matbus_gtfs_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(settings.matbus_gtfs_static_url)
        response.raise_for_status()
        target_zip.write_bytes(response.content)

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(target_dir)

    print(f"Downloaded MATBUS GTFS zip to {target_zip}")
    print(f"Extracted MATBUS GTFS files to {target_dir}")


if __name__ == "__main__":
    main()
