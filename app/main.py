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

    /* --- Streamlit branding elrejtése --- */
    #MainMenu                    { visibility: hidden; display: none; }
    .stDeployButton              { visibility: hidden; display: none; }
    footer                       { visibility: hidden; }

    /* --- Sidebar: minden gomb tiszta szövegként --- */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        border: none !important;
        padding: 0.12rem 0.4rem;
        font-size: 0.84rem;
        color: #c8cdd5;
        border-radius: 5px;
        min-height: unset;
        line-height: 1.4;
        text-align: left;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff;
    }

    /* --- Session sor: ikon oszlopok (✏️ 🗑️) alapból halványak --- */
    section[data-testid="stSidebar"]
        [data-testid="stVerticalBlockBorderWrapper"]
        [data-testid="column"]:nth-child(2) button,
    section[data-testid="stSidebar"]
        [data-testid="stVerticalBlockBorderWrapper"]
        [data-testid="column"]:nth-child(3) button {
        opacity: 0.12;
        transition: opacity 0.2s ease;
    }
    section[data-testid="stSidebar"]
        [data-testid="stVerticalBlockBorderWrapper"]:hover button {
        opacity: 1 !important;
    }

    /* --- "Új beszélgetés" gomb --- */
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background: #1a1d2a !important;
        border: 1px solid #4a4f60 !important;
        color: #ffffff !important;
        text-align: center !important;
        padding: 0.35rem 0.5rem !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background: #1e3a5f !important;
        border-color: #3b82f6 !important;
    }

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


def _delete_session(name):
    del st.session_state.chat_sessions[name]
    st.session_state.pop("editing_chat", None)
    if st.session_state.current_chat == name:
        keys = list(st.session_state.chat_sessions.keys())
        if keys:
            st.session_state.current_chat = keys[0]
        else:
            fallback = "Új beszélgetés 1"
            st.session_state.chat_sessions[fallback] = []
            st.session_state.current_chat = fallback
    st.rerun()


# --- Sidebar ---
with st.sidebar:
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = {"Új beszélgetés 1": []}
        st.session_state.current_chat = "Új beszélgetés 1"

    # --- Új beszélgetés ---
    st.markdown(
        "<p style='margin-bottom:0.2rem; font-weight:600; font-size:0.72rem; "
        "color:#6b7280; letter-spacing:0.06em;'>BESZÉLGETÉSEK</p>",
        unsafe_allow_html=True,
    )
    if st.button("+ Új beszélgetés", type="secondary", use_container_width=True):
        existing = [
            k for k in st.session_state.chat_sessions
            if k.startswith("Új beszélgetés ")
        ]
        nums = [
            int(k.rsplit(" ", 1)[-1]) for k in existing
            if k.rsplit(" ", 1)[-1].isdigit()
        ]
        next_num = max(nums) + 1 if nums else 1
        new_name = f"Új beszélgetés {next_num}"
        st.session_state.chat_sessions[new_name] = []
        st.session_state.current_chat = new_name
        st.rerun()

    st.markdown("---")

    # --- Beszélgetés lista ---
    for name in list(st.session_state.chat_sessions.keys()):
        editing = st.session_state.get("editing_chat") == name
        active = name == st.session_state.current_chat

        with st.container(border=True):
            if editing:
                new_name = st.text_input(
                    "",
                    value=name,
                    key=f"rename_{name}",
                    label_visibility="collapsed",
                )
                c_save, c_cancel = st.columns(2)
                with c_save:
                    if st.button("✅", key=f"save_{name}", use_container_width=True):
                        trimmed = new_name.strip()
                        if trimmed and trimmed != name and trimmed not in st.session_state.chat_sessions:
                            st.session_state.chat_sessions[trimmed] = (
                                st.session_state.chat_sessions.pop(name)
                            )
                            if active:
                                st.session_state.current_chat = trimmed
                        st.session_state.pop("editing_chat", None)
                        st.rerun()
                with c_cancel:
                    if st.button("❌", key=f"cancel_{name}", use_container_width=True):
                        st.session_state.pop("editing_chat", None)
                        st.rerun()
            else:
                label = f"▸ {name}" if active else name
                c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                with c1:
                    if st.button(label, key=f"session_{name}", use_container_width=True):
                        st.session_state.current_chat = name
                        st.rerun()
                with c2:
                    if st.button("✏️", key=f"edit_{name}"):
                        st.session_state.editing_chat = name
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"del_{name}"):
                        _delete_session(name)

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
messages = st.session_state.chat_sessions[st.session_state.current_chat]

for msg in messages:
    avatar = AVATAR_USER if msg["role"] == "user" else AVATAR_UNIBOT
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# --- Empty state: üdvözlő üzenet + javasolt kérdések ---
if not messages:
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
user_input = st.chat_input("Kérdezz a szabályzatokról...")

prompt = user_input
if "pending_prompt" in st.session_state and st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=AVATAR_USER):
        st.write(prompt)

    with st.chat_message("assistant", avatar=AVATAR_UNIBOT):
        try:
            with st.spinner("Keresés a szabályzatokban..."):
                docs = retriever.invoke(prompt)
                context = rag_engine.format_docs(docs)

                history = messages[-11:-1]
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
        messages.append({"role": "assistant", "content": ans})
        if len(messages) > 50:
            st.session_state.chat_sessions[st.session_state.current_chat] = messages[-50:]