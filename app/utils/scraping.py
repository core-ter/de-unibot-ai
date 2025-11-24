import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Settings
URL = "https://unideb.hu/szabalyzatok"

# Path setup
current_file_path = os.path.abspath(__file__)
current_dir_path = os.path.dirname(current_file_path)
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir_path))

# Handle edge case where root is 'app'
if os.path.basename(PROJECT_ROOT) == "app": 
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "data")

# Blacklist (broken/non-pdf files)
SKIP_FILES = [
    "Kooperatív Doktori Program Szabályzat 20210325.pdf",
]

def fetch_pdfs(url, folder):
    print(f"Parsing: {url}")
    print(f"Target: {folder}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Ensure folder exists
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    # Collect links
    links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.lower().endswith('.pdf'):
            links.append(urljoin(url, href))

    if not links:
        print("No PDFs found.")
        return

    print(f"Found {len(links)} PDFs. Downloading...")
    
    stats = {"dl": 0, "skip": 0, "fail": 0}

    for pdf_url in links:
        try:
            # Clean filename
            filename = requests.utils.unquote(pdf_url.split('/')[-1].split('?')[0])
        except:
            continue
            
        # Check blacklist
        if filename in SKIP_FILES:
            print(f"Skipping (Blacklisted): {filename}")
            stats["skip"] += 1
            continue

        target_path = os.path.join(folder, filename)

        if os.path.exists(target_path):
            continue

        print(f"Downloading: {filename}...")
        try:
            # Stream download
            with requests.get(pdf_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                
                # Verify content type
                if 'application/pdf' not in r.headers.get('Content-Type', '').lower():
                    print(f"Skipping (Not PDF): {filename}")
                    stats["skip"] += 1
                    continue

                with open(target_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): 
                        f.write(chunk)
            
            print(f"Saved: {filename}")
            stats["dl"] += 1
            
        except Exception as e:
            print(f"Error: {filename} - {e}")
            stats["fail"] += 1

    print(f"\nDone. Downloaded: {stats['dl']}, Skipped: {stats['skip']}, Failed: {stats['fail']}")

if __name__ == "__main__":
    fetch_pdfs(URL, DOWNLOAD_DIR)