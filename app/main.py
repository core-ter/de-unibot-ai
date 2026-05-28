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
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stChatInput input {
        background-color: #262730 !important;
        color: #fff !important;
        border: 1px solid #4e5d6c !important;
    }
    </style>
""", unsafe_allow_html=True)


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
        get_db.clear()
        st.cache_resource.clear()
        st.rerun()
    st.caption("Új PDF-ek hozzáadása után használd ezt a gombot.")

# --- Header ---
col1, col2 = st.columns([1, 5])
with col1:
    st.image(
        "https://unideb.hu/sites/default/files/upload_documents/de_cimer_sarga_kek_0.png",
        width=80,
    )
with col2:
    st.title("Unibot AI")
    st.caption("RAG alapú chatbot a Debreceni Egyetem szabályzataihoz")

# --- Init resources ---
vectorstore = get_db()
llm = get_ai()
retriever = vectorstore.as_retriever(
    search_kwargs={"k": config.NUM_RETRIEVED_DOCS}
)

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- User input ---
if prompt := st.chat_input("Kérdezz a szabályzatokról..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()

        try:
            with st.spinner("Keresés a szabályzatokban..."):
                docs = retriever.invoke(prompt)
                context = (
                    rag_engine.format_docs(docs) if docs else "Nincs információ."
                )

                history = st.session_state.messages[-11:-1]
                history_str = "\n".join(
                    f"{m['role']}: {m['content']}" for m in history
                )

                template = textwrap.dedent(f"""
                Te vagy az Unibot, a Debreceni Egyetem segédje.
                Válaszolj a kérdésre kizárólag a megadott szabályzatok alapján.
                Ha a szabályzatok nem tartalmaznak releváns információt,
                mondd meg őszintén, hogy nem tudsz válaszolni.

                Előzmények:
                {history_str}

                Szabályzatok (Forrás):
                {context}

                Kérdés: {prompt}
                """)

                resp = llm.invoke(template)
                ans = resp.content if hasattr(resp, "content") else str(resp)

        except Exception as e:
            st.error(f"Hiba történt: {e}")
            ans = "Bocs, valami félrement."

        placeholder.write(ans)

    if "hiba" not in ans.lower() and "félrement" not in ans.lower():
        st.session_state.messages.append({"role": "assistant", "content": ans})
        if len(st.session_state.messages) > 50:
            st.session_state.messages = st.session_state.messages[-50:]