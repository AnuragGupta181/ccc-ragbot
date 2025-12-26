# streamlit run src/frontend_streamlit.py

import sys
import os

# -----------------------------
# Fix Python path for Streamlit
# -----------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -----------------------------
# Imports
# -----------------------------
import streamlit as st
from uuid import uuid4
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

# 🔹 Import compiled LangGraph
from src.app import graph

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="CCC Intelligent Chatbot",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 CCC Intelligent Chatbot")
st.caption("Powered by LangGraph • RAG • Tools • Memory")

# -----------------------------
# Session State
# -----------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

config: RunnableConfig = {
    "configurable": {"thread_id": st.session_state.thread_id}
}

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("⚙️ Controls")

    if st.button("🔄 New Chat"):
        st.session_state.thread_id = str(uuid4())
        st.session_state.messages = []
        st.rerun()  # ✅ FIXED

    st.markdown("---")
    st.markdown("**Capabilities**")
    st.markdown(
        """
        - 🔍 RAG over CCC data  
        - 🌐 Web search  
        - ☁️ Weather info  
        - 🧠 Memory per thread  
        - 🧰 Tool-aware responses  
        """
    )

# -----------------------------
# Display Chat History
# -----------------------------
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])

# -----------------------------
# User Input
# -----------------------------
user_input = st.chat_input("Ask anything about Cloud Computing Cell...")

if user_input:
    # Save user message
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    # -------------------------
    # Assistant + Debug UI
    # -------------------------
    with st.chat_message("assistant"):
        answer_placeholder = st.empty()

    with st.expander("🧠 Execution Trace (Nodes & Tools)", expanded=False):
        debug_placeholder = st.empty()

    final_answer = ""
    debug_logs: list[str] = []

    # -------------------------
    # LangGraph Streaming
    # -------------------------
    for chunk in graph.stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    ):
        for node_name, update in chunk.items():

            debug_logs.append(f"🔹 **Node:** `{node_name}`")

            for msg in update["messages"]:

                # 🛠️ Tool messages
                if msg.__class__.__name__ == "ToolMessage":
                    debug_logs.append(
                        f"🛠️ **Tool Used:** `{msg.name}`"
                    )
                    debug_logs.append(
                        f"📤 **Tool Output:**\n```\n{msg.content}\n```"
                    )

                # 🤖 AI streaming (LIVE)
                elif isinstance(msg, AIMessage):
                    final_answer = msg.content
                    answer_placeholder.markdown(final_answer)

                # ✏️ Internal rewritten user message
                elif isinstance(msg, HumanMessage):
                    debug_logs.append(
                        f"✏️ **Internal User Message:** {msg.content}"
                    )

            # 🔄 Live debug update
            debug_placeholder.markdown("\n\n".join(debug_logs))

    # -------------------------
    # Save FINAL answer only
    # -------------------------
    st.session_state.messages.append(
        {"role": "assistant", "content": final_answer}
    )

# -----------------------------
# Footer
# -----------------------------
st.markdown(
    """
    <hr style="margin-top:2rem"/>
    <center>
    <small>CCC Chatbot • LangGraph • Streamlit UI</small>
    </center>
    """,
    unsafe_allow_html=True,
)
