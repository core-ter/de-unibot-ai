import os
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import config

def format_docs(docs: List[Document]) -> str:
    # Join docs with separator
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

def get_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

def get_llm() -> ChatGoogleGenerativeAI:
    if not config.GOOGLE_API_KEY:
        raise ValueError("Missing GOOGLE_API_KEY in .env")
        
    return ChatGoogleGenerativeAI(
        model=config.GENERATIVE_MODEL_NAME, 
        temperature=config.LLM_TEMPERATURE
    )

def build_or_load_vectorstore() -> Chroma:
    # Load or create vector DB
    embeddings = get_embedding_model()

    # Check if DB exists and has files
    if not os.path.exists(config.VEKTOR_DB_MAPPA) or not os.listdir(config.VEKTOR_DB_MAPPA):
        print(f"DB not found at {config.VEKTOR_DB_MAPPA}, creating new...")
        
        if not os.path.exists(config.PDF_DATA_PATH):
             raise FileNotFoundError(f"Data folder missing: {config.PDF_DATA_PATH}")

        # Load PDFs
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
            raise ValueError("No PDFs found to index!")

        # Split text
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE, 
            chunk_overlap=config.CHUNK_OVERLAP
        )
        splits = splitter.split_documents(docs)

        # Create DB
        vectorstore = Chroma.from_documents(
            documents=splits, 
            embedding=embeddings, 
            persist_directory=config.VEKTOR_DB_MAPPA
        )
    else:
        # Load existing DB
        vectorstore = Chroma(
            persist_directory=config.VEKTOR_DB_MAPPA, 
            embedding_function=embeddings
        )
    
    return vectorstore