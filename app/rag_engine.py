import os
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# --- JAVÍTÁS: ---
# 'from app import config' HELYETT sima 'import config'
# Mivel egy mappában vannak, így látják egymást.
import config

def format_docs(docs: List[Document]) -> str:
    """Segédfüggvény a dokumentumok szövegének összefűzésére."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

def get_embedding_model() -> HuggingFaceEmbeddings:
    """Betölti a konfigurált embedding modellt."""
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

def get_llm() -> ChatGoogleGenerativeAI:
    """Inicializálja a Gemini modellt a configban lévő kulccsal."""
    if not config.GOOGLE_API_KEY:
        raise ValueError("A GOOGLE_API_KEY nincs beállítva a .env fájlban!")
    return ChatGoogleGenerativeAI(
        model=config.GENERATIVE_MODEL_NAME, 
        temperature=config.LLM_TEMPERATURE
    )

def build_or_load_vectorstore() -> Chroma:
    """
    Létrehozza vagy betölti a vektoradatbázist.
    A config.VEKTOR_DB_MAPPA határozza meg a mentés helyét.
    """
    embeddings = get_embedding_model()

    # Ellenőrizzük, hogy létezik-e már az adatbázis
    if not os.path.exists(config.VEKTOR_DB_MAPPA) or not os.listdir(config.VEKTOR_DB_MAPPA):
        print(f"Vektor adatbázis nem található itt: {config.VEKTOR_DB_MAPPA}")
        
        # Ellenőrizzük, hogy van-e adat
        if not os.path.exists(config.PDF_DATA_PATH):
             raise FileNotFoundError(
                 f"A '{config.PDF_DATA_PATH}' mappa nem található! "
                 "Futtasd le a scrapert először."
             )

        # Használjuk a use_multithreading=False beállítást, ha a konzol teleszemetelése zavaró
        loader = DirectoryLoader(
            config.PDF_DATA_PATH, 
            glob="*.pdf", 
            loader_cls=PyPDFLoader,
            show_progress=False, 
            use_multithreading=True, 
            silent_errors=True
        )
        docs = loader.load()
        
        if not docs:
            raise ValueError(f"Nincs feldolgozható PDF fájl a '{config.PDF_DATA_PATH}' mappában!")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE, 
            chunk_overlap=config.CHUNK_OVERLAP
        )
        splits = text_splitter.split_documents(docs)

        vectorstore = Chroma.from_documents(
            documents=splits, 
            embedding=embeddings, 
            persist_directory=config.VEKTOR_DB_MAPPA
        )
    else:
        vectorstore = Chroma(
            persist_directory=config.VEKTOR_DB_MAPPA, 
            embedding_function=embeddings
        )
    
    return vectorstore