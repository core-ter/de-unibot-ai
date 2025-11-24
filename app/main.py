import streamlit as st
import textwrap

# Itt importáljuk a modulokat az 'app' csomagból
# Ez akkor működik, ha a projekt gyökeréből futtatod a 'streamlit run app/main.py' parancsot
import config
import rag_engine

# --- Page Configuration ---
st.set_page_config(
    page_title="Unibot - Debreceni Egyetem",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Custom CSS ---
custom_css = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    body { background-color: #1a1a1a; color: #e0e0e0; }
    .stApp { background-color: #1a1a1a; }
    .main-header { color: #50e050; text-align: center; font-size: 2.2rem; font-weight: bold; margin-bottom: 0.5rem; padding-top: 1rem; }
    .stCaption { color: #888888; text-align: center; }
    .stChatMessage { border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1rem; border: 1px solid #444; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    [data-testid="stChatMessage"][aria-label="human"] { background-color: #3a3a2a; border-color: #e0c050; }
    [data-testid="stChatMessage"][aria-label="human"] p { color: #f0e68c; }
    [data-testid="stChatMessage"][aria-label="assistant"] { background-color: #2a4a2a; border-color: #50e050; }
    [data-testid="stChatMessage"][aria-label="assistant"] p { color: #98fb98; }
    [data-testid="stChatMessage"][aria-label="assistant"] .stSpinner > div { border-top-color: #50e050; }
    .stSpinner { color: #98fb98; }
    [data-testid="stChatInput"] button { background-color: #50e050; color: #1a1a1a; border: none; border-radius: 8px; }
    [data-testid="stChatInput"] button:hover { background-color: #98fb98; color: #1a1a1a; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Resource Loading (Cached) ---

@st.cache_resource
def get_vectorstore():
    try:
        # Ez a hívás most már a rag_engine-en keresztül a HELYES (gyökér) mappát használja
        with st.spinner("Tudásbázis betöltése..."):
            return rag_engine.build_or_load_vectorstore()
    except Exception as e:
        st.error(f"Kritikus hiba az adatbázis betöltésekor: {e}")
        st.stop()

@st.cache_resource
def get_llm_client():
    try:
        return rag_engine.get_llm()
    except Exception as e:
        st.error(f"LLM hiba: {e}")
        st.stop()

# --- App Logic ---

st.markdown('<h1 class="main-header">🎓 DE-Unibot</h1>', unsafe_allow_html=True)

vectorstore = get_vectorstore()
llm = get_llm_client()
retriever = vectorstore.as_retriever(search_kwargs={"k": config.NUM_RETRIEVED_DOCS})

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Kérdezz a Debreceni Egyetem szabályzatairól..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)  # XSS védelem: st.write() escapeli a HTML-t

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            with st.spinner("Keresés a szabályzatokban..."):
                retrieved_docs = retriever.invoke(prompt)
                context_text = rag_engine.format_docs(retrieved_docs) if retrieved_docs else "(Nincs releváns találat.)"

                history_limit = 5
                relevant_history = st.session_state.messages[-(history_limit*2+1):-1]
                formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in relevant_history])

                prompt_template = textwrap.dedent(f"""
                A te szereped "Unibot", a Debreceni Egyetem segítőkész chatbotja. 
                Feladatod: segíteni a hallgatóknak a szabályzatokkal kapcsolatban.
                Legyél kedves, pontos és tömör.

                Korábbi beszélgetés (utolsó {history_limit} kör):
                {formatted_history}

                Releváns kontextus (elsődleges forrás):
                {context_text}

                Kérdés: {prompt}

                Válasz:
                """)

                response = llm.invoke(prompt_template)
                full_response = response.content if hasattr(response, 'content') else str(response)

        except Exception as e:
            st.error(f"Hiba történt: {e}")
            full_response = "Sajnálom, technikai hiba történt."

        message_placeholder.write(full_response)  # XSS védelem: st.write() escapeli a HTML-t

    if "hiba történt" not in full_response.lower():
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        
        # Memória limit: megakadályozzuk a végtelen növekedést hosszú beszélgetéseknél
        MAX_STORED_MESSAGES = 50
        if len(st.session_state.messages) > MAX_STORED_MESSAGES:
            st.session_state.messages = st.session_state.messages[-MAX_STORED_MESSAGES:]