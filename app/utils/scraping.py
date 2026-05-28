import hashlib
import json
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://unideb.hu/szabalyzatok"

current_file_path = os.path.abspath(__file__)
current_dir_path = os.path.dirname(current_file_path)
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir_path))

DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "data")
MANIFEST_PATH = os.path.join(DOWNLOAD_DIR, "download_manifest.json")

SKIP_FILES = [
    "Kooperatív Doktori Program Szabályzat 20210325.pdf",
]


def _hash_file(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _load_manifest() -> dict:
    if not os.path.isfile(MANIFEST_PATH):
        return {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(manifest: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def fetch_pdfs(url: str, folder: str) -> None:
    """
    Downloads PDFs with change detection.
    - Only re-downloads files whose remote checksum or filename differs
      from the last known state stored in download_manifest.json.
    - Skips already-known (identical) files completely.
    """
    print(f"Parsing: {url}")
    print(f"Target: {folder}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    os.makedirs(folder, exist_ok=True)

    links = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.lower().endswith(".pdf"):
            links.append(urljoin(url, href))

    if not links:
        print("No PDFs found.")
        return

    print(f"Found {len(links)} PDF links.")
    manifest = _load_manifest()
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    for pdf_url in links:
        try:
            fname = requests.utils.unquote(
                pdf_url.split("/")[-1].split("?")[0]
            )
        except Exception:
            continue

        if fname in SKIP_FILES:
            print(f"  [skip] Blacklisted: {fname}")
            stats["skipped"] += 1
            continue

        target = os.path.join(folder, fname)

        # --- Check local file ---
        if os.path.isfile(target):
            local_hash = _hash_file(target)
            # If the hash matches what we recorded, skip
            if manifest.get(fname) == local_hash:
                print(f"  [skip] Unchanged: {fname}")
                stats["skipped"] += 1
                continue
            # Hash differs → file was updated remotely; re-download
            print(f"  [update] Hash changed: {fname}")

        # --- Download ---
        print(f"  [download] {fname} ...")
        try:
            with requests.get(pdf_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                ct = r.headers.get("Content-Type", "").lower()
                if "application/pdf" not in ct:
                    print(f"  [skip] Not PDF (Content-Type={ct}): {fname}")
                    stats["skipped"] += 1
                    continue

                with open(target, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            # Record new hash
            manifest[fname] = _hash_file(target)
            _save_manifest(manifest)
            stats["downloaded"] += 1

        except Exception as e:
            print(f"  [fail] {fname}: {e}")
            stats["failed"] += 1

    # Clean up manifest: remove entries for files no longer on disk
    on_disk = set(os.listdir(folder))
    manifest = {k: v for k, v in manifest.items() if k in on_disk}
    _save_manifest(manifest)

    print(
        f"\nDone. Downloaded: {stats['downloaded']}, "
        f"Skipped: {stats['skipped']}, Failed: {stats['failed']}"
    )


if __name__ == "__main__":
    fetch_pdfs(URL, DOWNLOAD_DIR)