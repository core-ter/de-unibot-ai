import os
from dotenv import load_dotenv

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load env vars
load_dotenv(os.path.join(BASE_DIR, ".env"))

# API Key
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Directories
PDF_DATA_PATH = os.path.join(BASE_DIR, "data")
VEKTOR_DB_MAPPA = os.path.join(BASE_DIR, "chroma_db")

# Model Config
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GENERATIVE_MODEL_NAME = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.1

# RAG Settings
NUM_RETRIEVED_DOCS = 25
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 500