import os
import subprocess
import sys
import streamlit as st
import textwrap
import config
import rag_engine

st.set_page_config(
    page_title="Unibot - Debreceni Egyetem",
    page_icon="🎓",
    layout="centered",
)

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stChatInput input {
        background-color: #262730 !important;
        color: #fff !important;
        border: 1px solid #4e5d6c !important;
    }

    /* --- Streamlit márkajelzések elrejtése --- */
    #MainMenu          { visibility: hidden; }
    .stDeployButton    { visibility: hidden; }
    footer             { visibility: hidden; }
    header[data-testid="stHeader"] { visibility: hidden; }

    /* --- Üdvözlő szekció --- */
    .welcome-box {
        text-align: center;
        padding: 2rem 0;
    }
    .welcome-box h1 {
        font-size: 3rem;
        margin-bottom: 0.25rem;
    }
    .welcome-box p {
        color: #a0aec0;
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)

SUGGESTED_QUESTIONS = [
    "Hogyan működik a vizsgajelentkezés folyamata?",
    "Mik a kollégiumi házirend főbb pontjai?",
    "Milyen ösztöndíjak érhetők el a hallgatóknak?",
]

AVATAR_USER = "https://api.dicebear.com/7.x/notionists/svg?seed=Debrecen"
AVATAR_UNIBOT = "https://api.dicebear.com/7.x/bottts/svg?seed=Unibot&baseColor=1D4ED8"


def _stream_tokens(llm_stream):
    for chunk in llm_stream:
        text = getattr(chunk, "content", "")
        if text:
            yield text


@st.cache_resource
def ensure_data_folder() -> bool:
    """
    Ha a data/ mappa üres (pl. első Docker indítás), automatikusan
    letölti a PDF szabályzatokat a scraper segítségével.
    Sikertelen letöltés esetén st.stop()-pal leállítja az alkalmazást.
    """
    pdf_dir = config.PDF_DATA_PATH
    has_pdfs = (
        os.path.isdir(pdf_dir)
        and any(f.lower().endswith(".pdf") for f in os.listdir(pdf_dir))
    )
    if has_pdfs:
        return True

    with st.spinner(
        "Első indítás érzékelve: Szabályzatok letöltése "
        "és vektoradatbázis építése..."
    ):
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        scraper_script = os.path.join(
            project_root, "app", "utils", "scraping.py"
        )

        try:
            result = subprocess.run(
                [sys.executable, scraper_script],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=project_root,
            )
        except subprocess.TimeoutExpired:
            st.error(
                "A letöltés időtúllépés miatt megszakadt. "
                "Ellenőrizd a hálózati kapcsolatot, "
                "majd indítsd újra az alkalmazást."
            )
            st.stop()
        except FileNotFoundError:
            st.error(
                f"Nem található a Python futtatható: {sys.executable}"
            )
            st.stop()
        except Exception as e:
            st.error(f"Váratlan hiba a letöltés indításakor: {e}")
            st.stop()

        if result.returncode != 0:
            st.error(
                "Hiba a szabályzatok letöltése közben:\n\n"
                f"```\n{result.stderr or result.stdout}\n```"
            )
            st.stop()

        has_pdfs = (
            os.path.isdir(pdf_dir)
            and any(f.lower().endswith(".pdf") for f in os.listdir(pdf_dir))
        )
        if not has_pdfs:
            st.error(
                "A letöltés lefutott, de nem találhatók PDF fájlok "
                "a data/ mappában. Ellenőrizd a scraper kimenetét:\n\n"
                f"```\n{result.stdout}\n```"
            )
            st.stop()

    return True


@st.cache_resource
def get_db():
    return rag_engine.build_or_load_vectorstore()


@st.cache_resource
def get_ai():
    return rag_engine.get_llm()


# --- Sidebar ---
with st.sidebar:
    st.markdown("## Műveletek")
    if st.button("🔄 Adatbázis újraindítása"):
        ensure_data_folder.clear()
        get_db.clear()
        get_ai.clear()
        st.cache_resource.clear()
        st.rerun()
    st.caption("Új PDF-ek hozzáadása után használd ezt a gombot.")

# --- Header ---
st.markdown("""
    <div class="welcome-box">
        <h1>🎓 Unibot AI</h1>
        <p>RAG alapú chatbot a Debreceni Egyetem szabályzataihoz</p>
    </div>
""", unsafe_allow_html=True)

# --- Init resources ---
ensure_data_folder()
vectorstore = get_db()
llm = get_ai()
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": config.MMR_K,
        "fetch_k": config.MMR_FETCH_K,
        "lambda_mult": config.MMR_LAMBDA,
    },
)

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    avatar = AVATAR_USER if msg["role"] == "user" else AVATAR_UNIBOT
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# --- Empty state: üdvözlő üzenet + javasolt kérdések ---
if not st.session_state.messages:
    st.markdown(
        "<p style='text-align:center; color:#a0aec0; margin-top:1.5rem;'>"
        "Kérdezz bátran az egyetemi szabályzatokról, "
        "vagy válassz egyet az alábbiak közül:"
        "</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for i, question in enumerate(SUGGESTED_QUESTIONS):
        with cols[i]:
            if st.button(question, key=f"suggest_{i}", use_container_width=True):
                st.session_state.pending_prompt = question
                st.rerun()

# --- User input ---
# A st.chat_input NEM lehet feltételes blokkban – minden rendereléskor
# hívni kell, különben a widget eltűnik a DOM-ból.
user_input = st.chat_input("Kérdezz a szabályzatokról...")

prompt = user_input
if "pending_prompt" in st.session_state and st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=AVATAR_USER):
        st.write(prompt)

    with st.chat_message("assistant", avatar=AVATAR_UNIBOT):
        try:
            with st.spinner("Keresés a szabályzatokban..."):
                docs = retriever.invoke(prompt)
                context = rag_engine.format_docs(docs)

                history = st.session_state.messages[-11:-1]
                history_str = "\n".join(
                    f"{m['role']}: {m['content']}" for m in history
                )

                template = textwrap.dedent(f"""
                Te az "Unibot" vagy, a Debreceni Egyetem hallgatói AI
                asszisztense. Tegeződve, lazán, barátságosan, de
                tisztelettudóan kommunikálsz. Rövid, tömör, magyar
                egyetemista szóhasználattal válaszolj — nem jogi
                szakzsargonnal, de nem is slamposan.

                --- ALAPVETŐ TÁRSALGÁS ---
                Ha a felhasználó üzenete csak köszönés, bemutatkozás,
                vagy általános érdeklődés (pl. "Mit tudsz?"), NE
                hivatkozz az alábbi forrásokra. Röviden mutatkozz be
                és ajánld fel a segítséged.

                --- HIVATALOS SZABÁLYZATI KÉRDÉSEK ---
                Ha konkrét kérdés érkezik tanulmányi ügyekről,
                vizsgákról, szabályzatokról, felvételiről, kollégiumról,
                ösztöndíjról, doktori képzésről stb., SZIGORÚAN az
                alábbi szabályzatok alapján válaszolj.

                FONTOS SZABÁLYOK:
                - Mindig jelöld meg zárójelben, melyik szabályzatból
                  származik az információ, pl. "(Forrás: Tanulmányi és
                  Vizsgaszabályzat)".
                - Ha a szabályzatokban NINCS releváns információ,
                  mondd meg őszintén, és javasold a Tanulmányi Osztály
                  vagy az illetékes dékáni hivatal felkeresését.
                - NE találj ki semmit, amit a források nem támasztanak
                  alá!

                --- EDDIGI BESZÉLGETÉS ---
                {history_str}

                --- EGYETEMI SZABÁLYZATOK (HITELES FORRÁSOK) ---
                {context}

                --- KÉRDÉS ---
                {prompt}
                """)

            stream = _stream_tokens(llm.stream(template))
            ans = st.write_stream(stream)

        except Exception as e:
            st.error(f"Hiba történt: {e}")
            ans = "Bocs, valami félrement."

    if "hiba" not in ans.lower() and "félrement" not in ans.lower():
        st.session_state.messages.append({"role": "assistant", "content": ans})
        if len(st.session_state.messages) > 50:
            st.session_state.messages = st.session_state.messages[-50:]