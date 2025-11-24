import os
from dotenv import load_dotenv

# Útvonalak beállítása
# 1. __file__ = .../unibot_ai/app/config.py
# 2. dirname = .../unibot_ai/app
# 3. dirname(dirname) = .../unibot_ai  <-- EZ A HELYES GYÖKÉR
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Betöltjük a .env fájlt a projekt gyökeréből
load_dotenv(os.path.join(BASE_DIR, ".env"))

# API Kulcs
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Mappák (Abszolút útvonalak a BASE_DIR alapján)
# Így biztosan a gyökérben lévő 'data' és 'chroma_db' mappákat használja
PDF_DATA_PATH = os.path.join(BASE_DIR, "data")
VEKTOR_DB_MAPPA = os.path.join(BASE_DIR, "chroma_db")

# Modell Beállítások
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GENERATIVE_MODEL_NAME = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.1

# RAG Paraméterek
NUM_RETRIEVED_DOCS = 25
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 500