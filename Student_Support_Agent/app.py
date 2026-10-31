"""
Assignment 1: Intelligent Student Support Agent
Chat-style user interface built with Streamlit.
Directly enables students to ask questions about fees (in ₹ INR), scholarships, course changes, and handbook policies.
"""

import streamlit as st
import os
import sys

# Ensure local directory is on path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import validate_config
from database import init_db, get_all_students, get_student
from data.seed_demo_data import seed_database
from agent import StudentSupportAgent
from memory import get_memories
from tracing import get_traces

# --- Page Configuration ---
st.set_page_config(
    page_title="Intelligent Student Support Agent (Assignment 1)",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize Database ---
@st.cache_resource
def setup():
    init_db()
    seed_database()
    return validate_config()

is_valid, config_error = setup()

# --- Session State ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
if "selected_student_id" not in st.session_state:
    st.session_state.selected_student_id = "STU001"


def sidebar():
    """Render the sidebar with student profile selection and navigation."""
    st.sidebar.title("🎓 Student Portal")
    st.sidebar.caption("Assignment 1 — Intelligent Agent")
    st.sidebar.divider()

    # Student selector (Assignment 1: direct session selection)
    students = get_all_students()
    options = {f"{s['name']} ({s['student_id']})": s["student_id"] for s in students}
    
    selected_label = st.sidebar.selectbox(
        "Active Student Session",
        list(options.keys()),
        index=0
    )
    new_student_id = options[selected_label]
    if new_student_id != st.session_state.selected_student_id:
        st.session_state.selected_student_id = new_student_id
        st.session_state.chat_history = []
        st.rerun()

    student = get_student(st.session_state.selected_student_id)
    if student:
        st.sidebar.subheader(f"👤 {student['name']}")
        st.sidebar.caption(f"ID: `{student['student_id']}`")
        st.sidebar.caption(f"📚 {student['programme']}")

    st.sidebar.divider()
    st.sidebar.subheader("Navigation")
    
    if st.sidebar.button("💬 Chat Support", use_container_width=True):
        st.session_state.current_page = "chat"
        st.rerun()

    if st.sidebar.button("🧠 Agent Memory", use_container_width=True):
        st.session_state.current_page = "memory"
        st.rerun()

    if st.sidebar.button("🔍 Traces & Metrics", use_container_width=True):
        st.session_state.current_page = "traces"
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()


def chat_page():
    """Render the main chat interface."""
    st.title("💬 Student Support Chat")
    st.caption("Ask questions about fee status (in ₹ INR), scholarships, course change policies, or university calendar dates.")

    if not is_valid:
        st.error(f"⚠️ Configuration Error: {config_error}")
        st.info("Please set your GROQ_API_KEY in the `.env` file.")
        return

    # Display conversation messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat prompt
    if prompt := st.chat_input("Type your question here (e.g. 'What is my fee status?')..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing query and checking data..."):
                agent = StudentSupportAgent(student_id=st.session_state.selected_student_id)
                answer, trace = agent.process_query(prompt)
                st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})


def memory_page():
    """Render the student's persistent memory view."""
    st.title("🧠 Persistent Agent Memory")
    st.caption("Shows user-scoped preferences remembered across sessions (sensitive credentials like passwords/OTPs are filtered out).")

    memories = get_memories(st.session_state.selected_student_id)
    if not memories:
        st.info("No memories stored yet. The agent remembers preferences mentioned in chat.")
        return

    for m in memories:
        with st.container():
            st.write(f"**Key:** `{m['key']}`")
            st.write(f"**Value:** {m['value']}")
            st.caption(f"Last updated: {m['updated_at']}")
            st.divider()


def traces_page():
    """Render agent execution traces and latency/token measurements."""
    st.title("🔍 Traces & Observability")
    st.caption("Structured logs showing latency, token accounting, and tools called for each interaction.")

    traces = get_traces(student_id=st.session_state.selected_student_id)
    if not traces:
        st.info("No traces recorded yet for this session. Ask a question in the chat to view traces.")
        return

    for t in traces[:15]:
        with st.expander(f"Trace: {t.get('question', '')[:50]}... ({t.get('latency_ms', 0):.0f}ms)"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Latency", f"{t.get('latency_ms', 0):.0f}ms")
            c2.metric("Input Tokens", t.get("input_tokens") or "N/A")
            c3.metric("Output Tokens", t.get("output_tokens") or "N/A")
            
            st.write(f"**Selected Tool:** `{t.get('selected_tool', 'none')}`")
            if t.get("tool_arguments"):
                st.write("**Tool Arguments:**")
                st.code(t["tool_arguments"], language="json")
            if t.get("retrieved_evidence"):
                st.write("**Retrieved Evidence:**")
                st.code(t["retrieved_evidence"], language="json")
            st.write(f"**Final Answer:** {t.get('final_answer', '')}")


def main():
    sidebar()
    page = st.session_state.current_page
    if page == "chat":
        chat_page()
    elif page == "memory":
        memory_page()
    elif page == "traces":
        traces_page()


if __name__ == "__main__":
    main()

