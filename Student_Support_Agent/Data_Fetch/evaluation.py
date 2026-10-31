"""
Evaluation harness for Assignment 1: Intelligent Student Support Agent.
Runs baseline test queries, measures latency and tool usage, and generates a structured summary table.
"""

import os
import sys
import time
import logging
import tempfile
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import validate_config
from database import init_db
from data.seed_demo_data import seed_database
from agent import StudentSupportAgent
from memory import save_memory, get_memories
from tracing import get_traces

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EVALUATION_CASES = [
    {
        "id": "TC-01",
        "category": "Fee Status",
        "student_id": "STU001",
        "query": "What is my current fee balance and due date?",
        "expected_tool": "check_fee_status"
    },
    {
        "id": "TC-02",
        "category": "Scholarship",
        "student_id": "STU001",
        "query": "Can you check my scholarship details?",
        "expected_tool": "check_scholarship_status"
    },
    {
        "id": "TC-03",
        "category": "Support Ticket",
        "student_id": "STU002",
        "query": "I need help with my Big Data Analytics coursework registration. Please create a support request for me.",
        "expected_tool": "create_support_request"
    },
    {
        "id": "TC-04",
        "category": "Course Change",
        "student_id": "STU001",
        "query": "Can I switch my degree program to AI & Data Science? What is the deadline?",
        "expected_tool": "get_course_change_information"
    },
    {
        "id": "TC-05",
        "category": "Handbook RAG",
        "student_id": "STU001",
        "query": "What is the minimum attendance requirement to take semester exams?",
        "expected_tool": "search_handbook"
    },
    {
        "id": "TC-06",
        "category": "Session Start",
        "student_id": "STU001",
        "query": "When does the new academic session tentatively start?",
        "expected_tool": "search_handbook"
    }
]


def run_evaluation():
    """Run all benchmark test cases and output results."""
    is_valid, error = validate_config()
    if not is_valid:
        print(f"\n[WARNING] LLM evaluation skipped: {error}")
        print("To run live evaluation, configure a valid GROQ_API_KEY in assignment_1/.env\n")
        return None

    # Setup isolated temporary database
    db_path = os.path.join(tempfile.gettempdir(), f"eval_a1_{int(time.time())}.db")
    init_db(db_path)
    seed_database(db_path)

    results = []
    print("\nRunning Assignment 1 Evaluation Cases...")
    print("=" * 65)

    for tc in EVALUATION_CASES:
        agent = StudentSupportAgent(student_id=tc["student_id"])
        start_time = time.time()
        answer, trace = agent.process_query(
            query=tc["query"],
            test_case_id=tc["id"],
            db_path=db_path
        )
        elapsed = time.time() - start_time

        tool_matched = tc["expected_tool"] in (trace.selected_tool or "")
        results.append({
            "Case ID": tc["id"],
            "Category": tc["category"],
            "Student": tc["student_id"],
            "Expected Tool": tc["expected_tool"],
            "Selected Tool": trace.selected_tool or "None",
            "Tool Match": "PASS" if tool_matched else "FAIL",
            "Latency (ms)": round(trace.latency_ms, 2),
            "Success": trace.success
        })
        print(f"[{tc['id']}] {tc['category']} -> Tool: {trace.selected_tool} | Latency: {round(trace.latency_ms, 2)}ms | Match: {tool_matched}")

    df = pd.DataFrame(results)
    print("\n" + "=" * 65)
    print("ASSIGNMENT 1 BENCHMARK SUMMARY")
    print("=" * 65)
    print(df.to_string(index=False))

    # Clean up temp db
    try:
        os.remove(db_path)
    except OSError:
        pass

    return df


if __name__ == "__main__":
    run_evaluation()

