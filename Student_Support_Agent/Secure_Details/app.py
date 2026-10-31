"""
Streamlit Web Application for the Student Support Agent.
Provides login/logout, chat interface, approver dashboard,
audit log viewer, and trace viewer.
"""

import streamlit as st
import os
import sys
import json

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import validate_config
from database import init_db
from data.seed_demo_data import seed_database
from auth import authenticate, register_user
from authorization import is_approver
from agent import StudentSupportAgent
from memory import get_memories, save_memory
from approval import get_pending_approvals, approve_request, reject_request, get_student_approvals
from audit import get_audit_logs
from tracing import get_traces

# --- Page Configuration ---
st.set_page_config(
    page_title="Student Support Agent",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize Database ---
@st.cache_resource
def setup():
    init_db()
    seed_database()
    is_valid, error = validate_config()
    return is_valid, error

is_valid, config_error = setup()

# --- Session State Initialization ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "student_id" not in st.session_state:
    st.session_state.student_id = None
if "student_info" not in st.session_state:
    st.session_state.student_info = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"


def login_page():
    """Render the authentication page (Sign Up first, then Log In)."""
    st.title("🎓 Student Support Portal")
    st.caption("Sign up for a student account or log in with your credentials to access AI support.")
    
    if not is_valid:
        st.error(f"⚠️ Configuration Error: {config_error}")
        st.info("Please create a `.env` file with your GROQ_API_KEY. See `.env.example`.")
        return
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_signup, tab_login = st.tabs(["📝 Sign Up (New Students)", "🔑 Log In"])
        
        with tab_signup:
            st.markdown("### Create an Account")
            with st.form("signup_form"):
                signup_id = st.text_input("Choose Student ID *", placeholder="e.g., STU004")
                signup_name = st.text_input("Full Name *", placeholder="e.g., David Miller")
                signup_email = st.text_input("University Email *", placeholder="e.g., david.miller@university.edu")
                signup_programme = st.selectbox(
                    "Programme / Course *",
                    [
                        "PGDM in Big Data Analytics (BDA)",
                        "PGDM in AI & Data Science"
                    ]
                )
                signup_pass = st.text_input("Password (min 6 characters) *", type="password")
                signup_confirm = st.text_input("Confirm Password *", type="password")
                signup_submit = st.form_submit_button("📝 Register Account", use_container_width=True)
                
                if signup_submit:
                    if signup_pass != signup_confirm:
                        st.error("❌ Passwords do not match.")
                    else:
                        success, message = register_user(
                            student_id=signup_id,
                            name=signup_name,
                            email=signup_email,
                            password=signup_pass,
                            programme=signup_programme
                        )
                        if success:
                            st.session_state.signup_success_id = signup_id.strip().upper()
                            st.success(f"🎉 Account registered successfully! Please click the **🔑 Log In** tab to log in.")
                        else:
                            st.error(f"❌ {message}")
        
        with tab_login:
            st.markdown("### Log In")
            prefilled_id = st.session_state.get("signup_success_id", "")
            with st.form("login_form"):
                student_id = st.text_input("Student ID", value=prefilled_id, placeholder="e.g., STU001")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("🔑 Log In", use_container_width=True)
                
                if submitted:
                    if not student_id or not password:
                        st.error("Please enter both Student ID and Password.")
                    else:
                        user = authenticate(student_id.strip().upper(), password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.student_id = user["student_id"]
                            st.session_state.student_info = user
                            st.session_state.chat_history = []
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials. Please try again.")
            
            st.divider()
            st.caption("**Demo Accounts** (for demonstration only):")
            st.code(
                "STU001 / student123 (Alice - Big Data Analytics (BDA))\n"
                "STU002 / student456 (Bob - AI & Data Science)\n"
                "STU003 / student789 (Carol - AI & Data Science)\n"
                "ADMIN01 / admin123 (Dr. Sarah - Approver)",
                language=None
            )


def sidebar():
    """Render the sidebar with user info and navigation."""
    user = st.session_state.student_info
    
    st.sidebar.title("🎓 Student Support")
    st.sidebar.divider()
    
    # User info
    st.sidebar.subheader(f"👤 {user['name']}")
    st.sidebar.caption(f"ID: {user['student_id']} | Role: {user['role'].title()}")
    if user.get("programme"):
        st.sidebar.caption(f"📚 {user['programme']}")
    
    st.sidebar.divider()
    
    # Navigation
    st.sidebar.subheader("Navigation")
    
    if st.sidebar.button("💬 Chat", use_container_width=True):
        st.session_state.current_page = "chat"
        st.rerun()
    
    if st.sidebar.button("📋 My Approvals", use_container_width=True):
        st.session_state.current_page = "approvals"
        st.rerun()
    
    if is_approver(user["student_id"]):
        if st.sidebar.button("✅ Approver Dashboard", use_container_width=True):
            st.session_state.current_page = "approver"
            st.rerun()
    
    if st.sidebar.button("📊 Audit Logs", use_container_width=True):
        st.session_state.current_page = "audit"
        st.rerun()
    
    if st.sidebar.button("🔍 Traces", use_container_width=True):
        st.session_state.current_page = "traces"
        st.rerun()
    
    if st.sidebar.button("🧠 My Memory", use_container_width=True):
        st.session_state.current_page = "memory"
        st.rerun()
    
    st.sidebar.divider()
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.student_id = None
        st.session_state.student_info = None
        st.session_state.chat_history = []
        st.rerun()


def chat_page():
    """Render the chat interface."""
    st.title("💬 Student Support Chat")
    st.caption("Ask me about fees, scholarships, course changes, or university policies.")
    
    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your question here..."):
        # Display user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                agent = StudentSupportAgent(student_id=st.session_state.student_id)
                answer, trace = agent.process_query(prompt)
                
                st.markdown(answer)
        
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer
        })


def approvals_page():
    """Show the student's approval requests."""
    st.title("📋 My Approval Requests")
    
    approvals = get_student_approvals(st.session_state.student_id)
    
    if not approvals:
        st.info("You don't have any approval requests yet.")
        return
    
    for req in approvals:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(req["status"], "❓")
        
        with st.expander(f"{status_emoji} {req['action_type']} — {req['status'].upper()} ({req['created_at']})"):
            st.write(f"**Request ID:** `{req['request_id']}`")
            st.write(f"**Action Type:** {req['action_type']}")
            st.write(f"**Status:** {req['status']}")
            st.write(f"**Created:** {req['created_at']}")
            
            if isinstance(req.get("action_details"), dict):
                st.write(f"**Details:** {req['action_details'].get('correction_description', 'N/A')}")
            
            if req.get("resolved_at"):
                st.write(f"**Resolved:** {req['resolved_at']}")
            if req.get("resolution_notes"):
                st.write(f"**Notes:** {req['resolution_notes']}")


def approver_dashboard():
    """Render the approver dashboard for reviewing pending requests."""
    st.title("✅ Approver Dashboard")
    
    if not is_approver(st.session_state.student_id):
        st.error("⛔ Access denied. This page is for approvers only.")
        return
    
    pending = get_pending_approvals(st.session_state.student_id)
    
    if not pending:
        st.success("No pending approval requests.")
        return
    
    st.write(f"**{len(pending)} pending request(s)**")
    
    for req in pending:
        with st.expander(f"⏳ {req['action_type']} — Student: {req['student_id']} ({req['created_at']})"):
            st.write(f"**Request ID:** `{req['request_id']}`")
            st.write(f"**Student:** {req['student_id']}")
            st.write(f"**Action:** {req['action_type']}")
            
            if isinstance(req.get("action_details"), dict):
                st.json(req["action_details"])
            
            col1, col2 = st.columns(2)
            notes = st.text_input("Notes", key=f"notes_{req['request_id']}")
            
            with col1:
                if st.button(f"✅ Approve", key=f"approve_{req['request_id']}"):
                    result = approve_request(req["request_id"], st.session_state.student_id, notes)
                    if result.get("error"):
                        st.error(result["message"])
                    else:
                        st.success(result["message"])
                        st.rerun()
            
            with col2:
                if st.button(f"❌ Reject", key=f"reject_{req['request_id']}"):
                    result = reject_request(req["request_id"], st.session_state.student_id, notes)
                    if result.get("error"):
                        st.error(result["message"])
                    else:
                        st.warning(result["message"])
                        st.rerun()


def audit_page():
    """Render the audit log viewer with access controls."""
    st.title("📊 Audit Logs")
    
    user_id = st.session_state.student_id
    
    if is_approver(user_id):
        # Approvers can see all audit logs
        st.caption("Viewing all audit logs (approver access)")
        logs = get_audit_logs()
    else:
        # Students can only see their own logs
        st.caption("Viewing your audit logs only")
        logs = get_audit_logs(actor_id=user_id)
    
    if not logs:
        st.info("No audit logs available.")
        return
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        action_filter = st.selectbox("Filter by action", ["All"] + list(set(l.get("action", "") for l in logs)))
    with col2:
        decision_filter = st.selectbox("Filter by decision", ["All", "allowed", "denied", "pending"])
    
    filtered = logs
    if action_filter != "All":
        filtered = [l for l in filtered if l.get("action") == action_filter]
    if decision_filter != "All":
        filtered = [l for l in filtered if l.get("authorization_decision") == decision_filter]
    
    st.write(f"Showing {len(filtered)} of {len(logs)} entries")
    
    for log in filtered[:50]:
        decision_emoji = {"allowed": "✅", "denied": "❌", "pending": "⏳"}.get(
            log.get("authorization_decision", ""), "❓"
        )
        
        with st.expander(
            f"{decision_emoji} {log.get('action', 'N/A')} — {log.get('timestamp', 'N/A')}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Event ID:** `{log.get('event_id', 'N/A')}`")
                st.write(f"**Actor:** {log.get('actor_id', 'N/A')}")
                st.write(f"**Action:** {log.get('action', 'N/A')}")
                st.write(f"**Target:** {log.get('target_resource', 'N/A')}")
            with col2:
                st.write(f"**Auth Decision:** {log.get('authorization_decision', 'N/A')}")
                st.write(f"**Approval Status:** {log.get('approval_status', 'N/A')}")
                st.write(f"**Execution:** {log.get('execution_status', 'N/A')}")
                st.write(f"**Outcome:** {log.get('outcome', 'N/A')}")


def traces_page():
    """Render the trace viewer."""
    st.title("🔍 Agent Traces")
    
    user_id = st.session_state.student_id
    
    if is_approver(user_id):
        traces = get_traces()
        st.caption("Viewing all traces (approver access)")
    else:
        traces = get_traces(student_id=user_id)
        st.caption("Viewing your traces only")
    
    if not traces:
        st.info("No traces recorded yet. Start a chat conversation to generate traces.")
        return
    
    for trace in traces[:20]:
        success_emoji = "✅" if trace.get("success") else "❌"
        
        with st.expander(
            f"{success_emoji} {trace.get('question', 'N/A')[:60]}... — {trace.get('start_time', 'N/A')}"
        ):
            col1, col2, col3 = st.columns(3)
            col1.metric("Latency", f"{trace.get('latency_ms', 'N/A')}ms")
            col2.metric("Input Tokens", trace.get("input_tokens", "N/A"))
            col3.metric("Output Tokens", trace.get("output_tokens", "N/A"))
            
            st.write(f"**Trace ID:** `{trace.get('trace_id', 'N/A')}`")
            st.write(f"**Question:** {trace.get('question', 'N/A')}")
            st.write(f"**Tool:** {trace.get('selected_tool', 'None')}")
            
            if trace.get("tool_arguments"):
                st.write("**Tool Arguments:**")
                st.code(trace["tool_arguments"], language="json")
            
            if trace.get("retrieved_evidence"):
                st.write("**Retrieved Evidence:**")
                st.code(trace["retrieved_evidence"], language="json")
            
            st.write("**Answer:**")
            st.markdown(trace.get("final_answer", "N/A"))


def memory_page():
    """Render the memory viewer."""
    st.title("🧠 My Memory")
    st.caption("Non-sensitive preferences and context saved from your interactions.")
    
    memories = get_memories(st.session_state.student_id)
    
    if not memories:
        st.info("No memory entries yet. Interact with the chat to build your profile.")
        return
    
    for mem in memories:
        col1, col2, col3 = st.columns([2, 3, 2])
        col1.write(f"**{mem['key']}**")
        col2.write(mem['value'])
        col3.caption(mem.get('updated_at', 'N/A'))


# --- Main App Logic ---
def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        sidebar()
        
        page = st.session_state.current_page
        
        if page == "chat":
            chat_page()
        elif page == "approvals":
            approvals_page()
        elif page == "approver":
            approver_dashboard()
        elif page == "audit":
            audit_page()
        elif page == "traces":
            traces_page()
        elif page == "memory":
            memory_page()
        else:
            chat_page()


if __name__ == "__main__":
    main()
