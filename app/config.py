import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

PDF_DATA_PATH = os.path.join(BASE_DIR, "data")
VEKTOR_DB_MAPPA = os.path.join(BASE_DIR, "chroma_db")

# Többnyelvű (magyarra optimalizált) embedding modell CPU-ra.
# A MiniLM-L12 multilingual 50+ nyelvet támogat (köztük magyarul is),
# 384 dimenziós vektort ad, sebessége összemérhető az angol only változattal.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
GENERATIVE_MODEL_NAME = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.1

NUM_RETRIEVED_DOCS = 25

# Chunking: jogi/egyetemi szövegekhez igazított értékek.
# A nagyobb chunk (1500) megőrzi a szabályzatpontok teljes kontextusát,
# a 20%-os átfedés (300) biztosítja, hogy a határon lévő mondatok ne törjenek meg.
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300

# Magyar mondathatárok figyelembevételével bontunk:
# . ? ! után szóköz, majd sortörések, végül whitespace.
TEXT_SPLITTER_SEPARATORS = [
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    " ",
    "",
]

MANIFEST_FILE = "ingestion_manifest.json"