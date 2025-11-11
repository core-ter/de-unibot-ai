import streamlit as st
import os
import textwrap
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load environment variables (e.g., GOOGLE_API_KEY)
load_dotenv()

# --- Page Configuration (Themed) ---
st.set_page_config(
    page_title="Unibot - Debreceni Egyetem",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Custom CSS (Unchanged) ---
# (A CSS kódod változatlan maradt)
custom_css = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    body { background-color: #000000; }
    .stApp { background-color: #000000; }
    .main-header {
        color: #ffffff;
        text-align: center;
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
        padding: 1rem;
    }
    /* ... (a többi CSS szabályod) ... */
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# --- CONFIGURATION (Professionalized) ---
API_KEY = os.environ.get("GOOGLE_API_KEY")

# Use relative paths for GitHub compatibility
# Create a 'data' folder in your project for your PDFs
PDF_DATA_PATH = "./data" 
VEKTOR_DB_MAPPA = "./chroma_db"

# Model and RAG settings
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GENERATIVE_MODEL_NAME = "gemini-2.5-flash" # Correct, existing model
NUM_RETRIEVED_DOCS = 5 # Realistic number for RAG
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


# --- Helper Functions (English names) ---

def format_docs(docs: list) -> str:
    """Concatenates page content from a list of documents."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

def build_or_load_vectorstore(embeddings):
    """
    Loads the vector store from disk if it exists, otherwise builds
    it from the PDF documents in the data path.
    """
    if not os.path.exists(VEKTOR_DB_MAPPA) or not os.listdir(VEKTOR_DB_MAPPA):
        st.warning(f"Vektor adatbázis nem található. Új építése indul...")
        
        if not os.path.exists(PDF_DATA_PATH):
            st.error(f"Hiba: A '{PDF_DATA_PATH}' mappa nem található.")
            st.error("Kérlek, hozd létre a mappát és helyezd el benne a PDF fájlokat.")
            st.stop()

        with st.spinner(f"PDF-ek betöltése innen: '{PDF_DATA_PATH}'..."):
            loader = DirectoryLoader(
                PDF_DATA_PATH, glob="*.pdf", loader_cls=PyPDFLoader,
                show_progress=False, use_multithreading=True, silent_errors=True
            )
            docs = loader.load()
            if not docs:
                st.error(f"Hiba: Nincs PDF fájl a '{PDF_DATA_PATH}' mappában.")
                st.stop()

        with st.spinner(f"{len(docs)} dokumentum darabolása..."):
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE, 
                chunk_overlap=CHUNK_OVERLAP
            )
            splits = text_splitter.split_documents(docs)
            st.info(f"{len(splits)} szövegrészlet indexelésre előkészítve.")

        with st.spinner(f"Indexelés {len(splits)} szövegrészlettel..."):
            vectorstore = Chroma.from_documents(
                documents=splits, 
                embedding=embeddings, 
                persist_directory=VEKTOR_DB_MAPPA
            )
            st.success("Adatbázis sikeresen létrehozva és elmentve.")

    else:
        # Load existing database
        vectorstore = Chroma(
            persist_directory=VEKTOR_DB_MAPPA, 
            embedding_function=embeddings
        )
    return vectorstore


# --- Cached Resource Loaders (English names) ---

@st.cache_resource
def load_embedding_model():
    """Loads the HuggingFace embedding model."""
    try:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        return embeddings
    except Exception as e:
        st.error(f"Hiba az embedding modell betöltése közben: {e}")
        st.stop()

@st.cache_resource
def load_vector_db(_embeddings):
    """Loads or builds the vector database."""
    try:
        vectorstore = build_or_load_vectorstore(_embeddings)
        return vectorstore
    except Exception as e:
        st.error(f"Hiba az adatbázis kezelésekor: {e}")
        st.stop()

@st.cache_resource
def get_llm():
    """Initializes and returns the Generative AI model."""
    if not API_KEY:
        st.error("A GOOGLE_API_KEY nincs beállítva!")
        st.stop()
    try:
        llm = ChatGoogleGenerativeAI(model=GENERATIVE_MODEL_NAME, temperature=0.1)
        return llm
    except Exception as e:
        st.error(f"Hiba az LLM inicializálása közben: {e}")
        st.stop()

# --- Streamlit Application ---

# Page Header (Themed)
st.markdown('<h1 class="main-header">🎓 Unibot - Debreceni Egyetem</h1>', unsafe_allow_html=True)

# Load Resources
embeddings = load_embedding_model()
vectorstore = load_vector_db(embeddings)
llm = get_llm()

# Initialize Retriever
try:
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": NUM_RETRIEVED_DOCS}
    )
except Exception as e:
    st.error(f"Hiba a retriever létrehozása közben: {e}")
    st.stop()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input (Themed)
if prompt := st.chat_input("Kérdezz a Debreceni Egyetem szabályzatairól..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate AI response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        try:
            # Spinner text (Themed)
            with st.spinner("Keresés a szabályzatokban..."):
                # 1. Retrieve relevant documents
                retrieved_docs = retriever.invoke(prompt)
                context_text = format_docs(retrieved_docs) if retrieved_docs else "(Nem találtam releváns kontextust a dokumentumokban.)"

                # 2. Build the prompt (with history)
                history_limit = 5
                relevant_history = st.session_state.messages[-(history_limit*2+1):-1]
                formatted_history = "\n".join(
                    [f"{msg['role']}: {msg['content']}" for msg in relevant_history]
                )

                # --- Themed, Professional Prompt Template ---
                prompt_template = textwrap.dedent(f"""
                A te szereped "Unibot", a Debreceni Egyetem segítőkész chatbotja. 
                Feladatod: segíteni a hallgatóknak a Debreceni Egyetem szabályzataival kapcsolatos kérdésekben.
                
                Használd az alábbi kontextust és a korábbi beszélgetést a válaszadáshoz.
                Legyél kedves, pontos és tömör. Használhatsz emojikat.
                
                Ha a kontextus alapján nem tudsz válaszolni, jelezd, hogy az adott információt nem találod a szabályzatokban. 
                Ne találj ki információt.

                Korábbi beszélgetés (utolsó {history_limit} kör):
                {formatted_history}

                Releváns kontextus a dokumentumokból (ezt használd elsődlegesen):
                {context_text}

                Aktuális kérdés:
                {prompt}

                Válasz (csak a válasz szövegét add meg):
                """)
                # --- End of Prompt Template ---

                # 3. Call the LLM
                response = llm.invoke(prompt_template)
                full_response = response.content if hasattr(response, 'content') else str(response)

        except Exception as e:
            st.error(f"Hiba a válasz generálása közben: {e}")
            full_response = "Sajnálom, hiba történt a válasz generálása során. Kérlek, próbáld újra."

        # Display the full response
        message_placeholder.markdown(full_response)

    # Update chat history (only if not an error)
    if "hiba történt" not in full_response.lower():
        st.session_state.messages.append({"role": "assistant", "content": full_response})