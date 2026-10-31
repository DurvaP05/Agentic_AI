"""
Tracing module for the Student Support Agent.
Records structured traces for every agent interaction,
including tools, latency, token usage, and outcomes.
"""

import uuid
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from database import get_db

logger = logging.getLogger(__name__)


@dataclass
class Trace:
    """Structured trace for an agent interaction."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    test_case_id: str = ""
    student_id: str = ""
    question: str = ""
    selected_tool: str = ""
    tool_arguments: str = ""
    tool_result: str = ""
    retrieved_evidence: str = ""
    memory_used: str = ""
    start_time: str = ""
    end_time: str = ""
    latency_ms: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    final_answer: str = ""
    success: bool = False


def start_trace(test_case_id="", student_id="", question=""):
    """Start a new trace for an agent interaction.
    
    Args:
        test_case_id: Optional test case identifier.
        student_id: The student's ID (or pseudonym).
        question: The student's question.
        
    Returns:
        Trace: A new trace with start time set.
    """
    trace = Trace(
        test_case_id=test_case_id,
        student_id=student_id,
        question=question,
        start_time=datetime.now().isoformat()
    )
    logger.info(f"Trace started: {trace.trace_id}")
    return trace


def end_trace(trace, selected_tool="", tool_arguments=None, tool_result=None,
              retrieved_evidence=None, memory_used=None, final_answer="",
              input_tokens=None, output_tokens=None, success=True):
    """Complete a trace with results and timing.
    
    Args:
        trace: The trace to complete.
        selected_tool: The tool that was selected.
        tool_arguments: Tool arguments (dict or string).
        tool_result: Tool execution result (dict or string).
        retrieved_evidence: Retrieved handbook chunks.
        memory_used: Memory entries used (without sensitive data).
        final_answer: The agent's final answer.
        input_tokens: Input tokens used (from API response).
        output_tokens: Output tokens used (from API response).
        success: Whether the interaction was successful.
        
    Returns:
        Trace: The completed trace.
    """
    trace.end_time = datetime.now().isoformat()
    trace.selected_tool = selected_tool or trace.selected_tool
    trace.tool_arguments = _safe_json(tool_arguments) if tool_arguments else trace.tool_arguments
    trace.tool_result = _safe_json(tool_result) if tool_result else trace.tool_result
    trace.retrieved_evidence = _safe_json(retrieved_evidence) if retrieved_evidence else trace.retrieved_evidence
    trace.memory_used = _safe_json(memory_used) if memory_used else trace.memory_used
    trace.final_answer = final_answer or trace.final_answer
    trace.input_tokens = input_tokens
    trace.output_tokens = output_tokens
    trace.success = success
    
    # Calculate latency
    if trace.start_time and trace.end_time:
        try:
            start = datetime.fromisoformat(trace.start_time)
            end = datetime.fromisoformat(trace.end_time)
            trace.latency_ms = round((end - start).total_seconds() * 1000, 2)
        except (ValueError, TypeError):
            trace.latency_ms = 0.0
    
    logger.info(f"Trace ended: {trace.trace_id}, latency={trace.latency_ms}ms, success={success}")
    return trace


def save_trace(trace, db_path=None):
    """Persist a trace to the database.
    
    Args:
        trace: The Trace to save.
        db_path: Optional database path.
    """
    conn = get_db(db_path)
    try:
        conn.execute(
            """INSERT INTO traces 
               (trace_id, test_case_id, student_id, question, selected_tool,
                tool_arguments, tool_result, retrieved_evidence, memory_used,
                start_time, end_time, latency_ms, input_tokens, output_tokens,
                final_answer, success)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trace.trace_id, trace.test_case_id, trace.student_id, trace.question,
             trace.selected_tool, trace.tool_arguments, trace.tool_result,
             trace.retrieved_evidence, trace.memory_used,
             trace.start_time, trace.end_time, trace.latency_ms,
             trace.input_tokens, trace.output_tokens,
             trace.final_answer, int(trace.success))
        )
        conn.commit()
        logger.info(f"Trace saved to database: {trace.trace_id}")
    except Exception as e:
        logger.error(f"Failed to save trace: {e}")
    finally:
        conn.close()


def get_traces(student_id=None, test_case_id=None, limit=100, db_path=None):
    """Retrieve stored traces with optional filters.
    
    Args:
        student_id: Filter by student ID.
        test_case_id: Filter by test case ID.
        limit: Maximum records to return.
        db_path: Optional database path.
        
    Returns:
        list[dict]: List of trace records.
    """
    conn = get_db(db_path)
    try:
        query = "SELECT * FROM traces WHERE 1=1"
        params = []
        
        if student_id:
            query += " AND student_id = ?"
            params.append(student_id)
        
        if test_case_id:
            query += " AND test_case_id = ?"
            params.append(test_case_id)
        
        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def trace_to_dict(trace):
    """Convert a Trace to a dictionary.
    
    Args:
        trace: Trace object.
        
    Returns:
        dict: Trace fields as dict.
    """
    return asdict(trace)


def _safe_json(obj):
    """Safely convert an object to a JSON string.
    
    Args:
        obj: Object to serialize.
        
    Returns:
        str: JSON string representation.
    """
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)
