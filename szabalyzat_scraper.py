import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Target URL
BASE_URL = "https://unideb.hu/szabalyzatok" 

# Relative path based on the script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "szabalyzatok")

def fetch_pdfs(url, folder):
    """Downloads all PDFs to the target folder."""
    
    print(f"Parsing page: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
    except requests.exceptions.RequestException as e:
        print(f"Error (page unreachable?): {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Create folder
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

    for pdf_url in links_to_download:
        try:
            filename = pdf_url.split('/')[-1].split('?')[0]
        except Exception:
            print(f"Invalid URL, skipping: {pdf_url}")
            continue
            
        target_path = os.path.join(folder, filename)

        if os.path.exists(target_path):
            print(f"Already exists: {filename}")
            continue

        print(f"Saving: {filename}...")
        try:
            pdf_response = requests.get(pdf_url, stream=True, timeout=60)
            pdf_response.raise_for_status()

            with open(target_path, 'wb') as f:
                for chunk in pdf_response.iter_content(chunk_size=8192): 
                    f.write(chunk)
            
            dl_count += 1

        except requests.exceptions.RequestException as e:
            print(f"!!! Error ({filename}): {e}")
            fail_count += 1

    print("\n" + "="*20)
    print(f"Done. Successful: {dl_count}, Failed: {fail_count}.")
    print(f"Folder: {os.path.abspath(folder)}")
    print("="*20)

if __name__ == "__main__":
    fetch_pdfs(BASE_URL, DOWNLOAD_DIR)