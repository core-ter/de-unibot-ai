import hashlib
import json
import os
from typing import Dict, List

from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config


def _hash_file(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _scan_data_folder() -> Dict[str, str]:
    """Returns {filename: sha256_hash} for all PDFs in data/."""
    if not os.path.isdir(config.PDF_DATA_PATH):
        return {}
    out = {}
    for fname in os.listdir(config.PDF_DATA_PATH):
        if fname.lower().endswith(".pdf"):
            fpath = os.path.join(config.PDF_DATA_PATH, fname)
            out[fname] = _hash_file(fpath)
    return out


def _load_manifest() -> Dict[str, str]:
    path = os.path.join(config.VEKTOR_DB_MAPPA, config.MANIFEST_FILE)
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(manifest: Dict[str, str]) -> None:
    os.makedirs(config.VEKTOR_DB_MAPPA, exist_ok=True)
    path = os.path.join(config.VEKTOR_DB_MAPPA, config.MANIFEST_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _get_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=config.TEXT_SPLITTER_SEPARATORS,
    )


def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def get_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)


def get_llm() -> ChatGoogleGenerativeAI:
    if not config.GOOGLE_API_KEY:
        raise ValueError("Missing GOOGLE_API_KEY in .env")
    return ChatGoogleGenerativeAI(
        model=config.GENERATIVE_MODEL_NAME, temperature=config.LLM_TEMPERATURE
    )


def _full_rebuild(embeddings: HuggingFaceEmbeddings) -> Chroma:
    """Drop and rebuild the entire vector DB from scratch."""
    print(f"[RAG] Full rebuild from {config.PDF_DATA_PATH} ...")

    if not os.path.isdir(config.PDF_DATA_PATH):
        raise FileNotFoundError(f"Data folder missing: {config.PDF_DATA_PATH}")

    loader = DirectoryLoader(
        config.PDF_DATA_PATH,
        glob="*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=False,
        use_multithreading=True,
        silent_errors=True,
    )
    docs = loader.load()
    if not docs:
        raise ValueError("No PDFs found to index!")

    # Embed source filename into metadata for later incremental tracking
    for d in docs:
        fname = os.path.basename(d.metadata.get("source", ""))
        d.metadata["source_file"] = fname

    splitter = _get_splitter()
    splits = splitter.split_documents(docs)

    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=config.VEKTOR_DB_MAPPA,
    )

    # Save fresh manifest
    _save_manifest(_scan_data_folder())
    print("[RAG] Full rebuild done.")
    return vectorstore


def _incremental_update(
    vectorstore: Chroma, embeddings: HuggingFaceEmbeddings
) -> None:
    """Add/update/delete only changed PDFs."""
    current = _scan_data_folder()
    previous = _load_manifest()

    added_or_changed = {
        f for f, h in current.items() if previous.get(f) != h
    }
    deleted = set(previous.keys()) - set(current.keys())

    if not added_or_changed and not deleted:
        print("[RAG] No changes detected, skipping update.")
        return

    print(
        f"[RAG] Changes: +{len(added_or_changed - set(previous.keys()))} new, "
        f"~{len(added_or_changed & set(previous.keys()))} updated, "
        f"-{len(deleted)} deleted"
    )

    collection = vectorstore._collection
    splitter = _get_splitter()

    for fname in sorted(added_or_changed):
        fpath = os.path.join(config.PDF_DATA_PATH, fname)
        if not os.path.isfile(fpath):
            continue

        # Remove old chunks for this file (if any)
        try:
            existing = collection.get(where={"source_file": fname})
            if existing.get("ids"):
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

        loader = PyPDFLoader(fpath)
        docs = loader.load()
        for d in docs:
            d.metadata["source_file"] = fname
        splits = splitter.split_documents(docs)
        if splits:
            vectorstore.add_documents(splits)
            print(f"[RAG]   indexed: {fname} ({len(splits)} chunks)")

    for fname in sorted(deleted):
        try:
            existing = collection.get(where={"source_file": fname})
            if existing.get("ids"):
                collection.delete(ids=existing["ids"])
                print(f"[RAG]   removed: {fname}")
        except Exception:
            pass

    _save_manifest(current)
    print("[RAG] Incremental update done.")


def build_or_load_vectorstore() -> Chroma:
    """
    Smart initialisation: incremental update when possible,
    full rebuild otherwise, just load when nothing changed.
    """
    embeddings = get_embedding_model()

    if not os.path.isdir(config.VEKTOR_DB_MAPPA) or not os.listdir(
        config.VEKTOR_DB_MAPPA
    ):
        return _full_rebuild(embeddings)

    vectorstore = Chroma(
        persist_directory=config.VEKTOR_DB_MAPPA,
        embedding_function=embeddings,
    )

    current = _scan_data_folder()
    previous = _load_manifest()

    if not previous or current != previous:
        _incremental_update(vectorstore, embeddings)

    return vectorstore