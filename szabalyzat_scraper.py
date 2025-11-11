import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- Beállítások ---

# Az URL, ahonnan a szabályzatokat szeretnéd letölteni
URL = "https://unideb.hu/szabalyzatok" 

# A mappa neve, ahova a letöltött PDF-eket menteni szeretnéd
# Ez a mappa létrejön a szkript futtatási helyén, ha még nem létezik.
LETOLTESI_MAPPA = r"E:\Munka\unibot_ai\szabalyzatok"

# --- Kód ---

def letolt_szabalyzatok(url, mappa):
    """
    Letölti az összes PDF linket a megadott URL-ről a megadott mappába.
    """
    print(f"Weboldal lekérése: {url}")
    try:
        response = requests.get(url, timeout=30) # 30 másodperc timeout
        response.raise_for_status() # Hibát dob, ha a lekérés sikertelen (pl. 404)
        response.encoding = response.apparent_encoding # Próbálja kitalálni a helyes karakterkódolást
        
    except requests.exceptions.RequestException as e:
        print(f"Hiba a weboldal lekérése közben: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Mappa létrehozása, ha nem létezik
    if not os.path.exists(mappa):
        print(f"Létrehozom a mappát: '{mappa}'")
        os.makedirs(mappa)

    pdf_linkek = []
    # Az összes link ('a' tag) megkeresése
    for link in soup.find_all('a', href=True):
        href = link['href']
        # Csak azokat vesszük figyelembe, amik '.pdf'-re végződnek (kis/nagybetű érzéketlen)
        if href.lower().endswith('.pdf'):
            # Teljes URL létrehozása (kezeli a relatív linkeket is)
            teljes_url = urljoin(url, href)
            pdf_linkek.append(teljes_url)

    if not pdf_linkek:
        print("Nem találtam PDF linkeket az oldalon.")
        return

    print(f"Összesen {len(pdf_linkek)} PDF link található.")
    
    letoltott_db = 0
    hibas_db = 0

    for pdf_url in pdf_linkek:
        # A fájlnév kinyerése az URL végéről
        fajlnev = pdf_url.split('/')[-1]
        cel_utvonal = os.path.join(mappa, fajlnev)

        # Ha a fájl már létezik, kihagyjuk (opcionális, de hasznos)
        if os.path.exists(cel_utvonal):
            print(f"Kihagyva (már létezik): {fajlnev}")
            continue

        print(f"Letöltés indul: {fajlnev} innen: {pdf_url}")
        try:
            pdf_response = requests.get(pdf_url, stream=True, timeout=60) # Hosszabb timeout letöltéshez
            pdf_response.raise_for_status()

            # Fájl írása darabokban (nagy fájlok esetén is működik)
            with open(cel_utvonal, 'wb') as f:
                for chunk in pdf_response.iter_content(chunk_size=8192): 
                    f.write(chunk)
            
            print(f"Sikeres letöltés: {fajlnev}")
            letoltott_db += 1

        except requests.exceptions.RequestException as e:
            print(f"!!! Hiba a letöltés közben ({fajlnev}): {e}")
            hibas_db += 1
        except Exception as e:
             print(f"!!! Váratlan hiba ({fajlnev}): {e}")
             hibas_db += 1


    print("\n--- Összegzés ---")
    print(f"Sikeresen letöltve: {letoltott_db} fájl")
    print(f"Hibás letöltések: {hibas_db} fájl")
    print(f"Letöltési mappa: '{os.path.abspath(mappa)}'")

# --- A szkript futtatása ---
if __name__ == "__main__":
    letolt_szabalyzatok(URL, LETOLTESI_MAPPA)