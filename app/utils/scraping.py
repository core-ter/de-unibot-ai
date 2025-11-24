import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- Settings ---
URL = "https://unideb.hu/szabalyzatok"

# --- Path Logic (Smart Detection) ---
# Ez a rész biztosítja, hogy a 'data' mappa mindig a projekt gyökerébe kerüljön,
# akkor is, ha ez a fájl az 'app/utils' mappában van.

current_file_path = os.path.abspath(__file__)
current_dir_path = os.path.dirname(current_file_path) # .../app/utils

# Feltételezzük, hogy a struktúra: unibot_ai/app/utils/scraping.py
# Ezért 3 szintet kell visszalépni a fájltól, vagy 2 szintet a mappától.
# 1. fel: .../app
# 2. fel: .../unibot_ai (PROJEKT GYÖKÉR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir_path))

# Ha esetleg a gyökérben lenne a fájl (régi struktúra), akkor korrigálunk:
if os.path.basename(PROJECT_ROOT) == "app": 
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

# A célmappa: unibot_ai/data
DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "data")

# --- Blacklist ---
# Fájlok, amik hibásak vagy nem PDF-ek, ezért kihagyjuk őket
SKIP_FILES = [
    "Kooperatív Doktori Program Szabályzat 20210325.pdf",
]

def fetch_pdfs(url, folder):
    """Downloads all PDFs to the target folder."""
    
    print(f"Parsing page: {url}")
    print(f"Target folder: {folder}") # Ellenőrzés: E:\Munka\unibot_ai\data

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
    except requests.exceptions.RequestException as e:
        print(f"Error (page unreachable?): {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Create folder if it doesn't exist
    if not os.path.exists(folder):
        print(f"Creating folder: '{folder}'")
        os.makedirs(folder, exist_ok=True)

    links_to_download = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.lower().endswith('.pdf'):
            full_url = urljoin(url, href)
            links_to_download.append(full_url)

    if not links_to_download:
        print("No PDF links found on the page.")
        return

    print(f"Found {len(links_to_download)} total PDFs. Starting download...")
    
    dl_count = 0
    fail_count = 0
    skip_count = 0

    for pdf_url in links_to_download:
        try:
            # Clean filename
            filename = pdf_url.split('/')[-1].split('?')[0]
            filename = requests.utils.unquote(filename)
        except Exception:
            print(f"Invalid URL, skipping: {pdf_url}")
            continue
            
        # --- SKIP LIST CHECK ---
        if filename in SKIP_FILES:
            print(f" >>> SKIPPING (Blacklisted): {filename}")
            skip_count += 1
            continue

        target_path = os.path.join(folder, filename)

        if os.path.exists(target_path):
            # print(f"Already exists: {filename}") # Opcionális: kevésbé zajos kimenetért
            continue

        print(f"Downloading: {filename}...")
        try:
            # 1. Check Content-Type first (HEAD request logic via stream)
            pdf_response = requests.get(pdf_url, stream=True, timeout=60)
            pdf_response.raise_for_status()

            content_type = pdf_response.headers.get('Content-Type', '').lower()
            if 'application/pdf' not in content_type:
                print(f" >>> SKIPPING: Not a PDF! (Type: {content_type}) - {filename}")
                skip_count += 1
                continue

            # 2. Save file
            with open(target_path, 'wb') as f:
                for chunk in pdf_response.iter_content(chunk_size=8192): 
                    f.write(chunk)
            
            print(f"Saved: {filename}")
            dl_count += 1
            
        except Exception as e:
            print(f"!!! Error downloading {filename}: {e}")
            fail_count += 1

    print("\n" + "="*30)
    print(f"Done.")
    print(f"Downloaded: {dl_count}")
    print(f"Skipped: {skip_count}")
    print(f"Failed: {fail_count}")
    print(f"Location: {os.path.abspath(folder)}")
    print("="*30)

if __name__ == "__main__":
    fetch_pdfs(URL, DOWNLOAD_DIR)