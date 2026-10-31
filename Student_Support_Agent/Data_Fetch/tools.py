"""
Tool implementations for Assignment 1 - Intelligent Student Support Agent.
Provides functions callable by the LLM for fee inquiries, scholarships, course changes, and handbook retrieval.
"""

import json
import logging
from database import (
    get_student,
    get_fee_status,
    get_scholarship_status,
    create_support_request_record,
)
from retrieval import HandbookRetriever

logger = logging.getLogger(__name__)

_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HandbookRetriever()
    return _retriever


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_fee_status",
            "description": "Retrieves the student's fee status including total fees, paid amount, due amount (in ₹ INR), payment status, and due date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID to look up (e.g. STU001)."
                    }
                },
                "required": ["student_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_scholarship_status",
            "description": "Retrieves the student's scholarship status including scholarship name, award amount (in ₹ INR), status, and active dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID to look up (e.g. STU001)."
                    }
                },
                "required": ["student_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_request",
            "description": "Creates a new support ticket for the student across categories: academic, financial, technical, administrative, wellbeing, general.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID creating the request."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["academic", "financial", "technical", "administrative", "wellbeing", "general"],
                        "description": "Category of the support ticket."
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the issue or request."
                    }
                },
                "required": ["student_id", "category", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_course_change_information",
            "description": "Retrieves relevant course change guidance, add/drop windows, and programme transfer rules from the student handbook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The specific question about course changes or add/drop."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_handbook",
            "description": "Searches the student handbook for academic calendar dates, session start dates, deadlines, fee policies, exams, and institutional rules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant policies or dates."
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def check_fee_status(student_id, db_path=None):
    """Retrieve fee status for a student."""
    if not student_id:
        return {"error": True, "message": "student_id is required"}
    
    fee = get_fee_status(student_id, db_path)
    if fee is None:
        return {"error": False, "message": f"No fee record found for student {student_id}.", "data": None}
    
    return {
        "error": False,
        "message": "Fee status retrieved successfully.",
        "data": {
            "student_id": student_id,
            "currency": "INR (₹)",
            "total_fees": fee["total_fees"],
            "paid_amount": fee["paid_amount"],
            "due_amount": fee["due_amount"],
            "due_date": fee["due_date"],
            "payment_status": fee["payment_status"],
            "last_payment_date": fee["last_payment_date"]
        }
    }


def check_scholarship_status(student_id, db_path=None):
    """Retrieve scholarship status for a student."""
    if not student_id:
        return {"error": True, "message": "student_id is required"}
    
    scholarship = get_scholarship_status(student_id, db_path)
    if scholarship is None:
        return {"error": False, "message": f"No active scholarship found for student {student_id}.", "data": None}
    
    return {
        "error": False,
        "message": "Scholarship status retrieved successfully.",
        "data": {
            "student_id": student_id,
            "currency": "INR (₹)",
            "scholarship_name": scholarship["scholarship_name"],
            "amount": scholarship["amount"],
            "status": scholarship["status"],
            "awarded_date": scholarship["awarded_date"],
            "expiry_date": scholarship["expiry_date"]
        }
    }


def create_support_request(student_id, category, description, db_path=None):
    """Create a new support request."""
    if not student_id or not category or not description:
        return {"error": True, "message": "Missing required fields (student_id, category, description)"}
    
    ticket_id = create_support_request_record(student_id, category, description, db_path)
    return {
        "error": False,
        "message": f"Support request created successfully. Ticket ID: #{ticket_id}",
        "data": {
            "ticket_id": ticket_id,
            "student_id": student_id,
            "category": category,
            "status": "open"
        }
    }


def get_course_change_information(query="course change", db_path=None):
    """Retrieve course change policies from the handbook."""
    retriever = _get_retriever()
    results = retriever.retrieve(query, top_k=3)
    if not results:
        return {
            "error": False,
            "message": "The handbook does not contain sufficient details on this course change query.",
            "data": None
        }
    return {
        "error": False,
        "message": "Course change guidance retrieved.",
        "data": [{"section": r["section"], "content": r["text"]} for r in results]
    }


def search_handbook(query, db_path=None):
    """Search handbook for policies or calendar dates."""
    retriever = _get_retriever()
    results = retriever.retrieve(query, top_k=5)
    if not results:
        return {
            "error": False,
            "message": "The student handbook does not contain enough information for this query.",
            "data": None
        }
    return {
        "error": False,
        "message": "Relevant handbook sections retrieved.",
        "data": [{"section": r["section"], "content": r["text"], "relevance": r["score"]} for r in results]
    }


def execute_tool(tool_name, arguments, db_path=None):
    """Execute a tool by name with arguments."""
    try:
        if tool_name == "check_fee_status":
            return check_fee_status(arguments.get("student_id"), db_path=db_path)
        elif tool_name == "check_scholarship_status":
            return check_scholarship_status(arguments.get("student_id"), db_path=db_path)
        elif tool_name == "create_support_request":
            return create_support_request(
                arguments.get("student_id"),
                arguments.get("category"),
                arguments.get("description"),
                db_path=db_path
            )
        elif tool_name == "get_course_change_information":
            return get_course_change_information(arguments.get("query", "course change"), db_path=db_path)
        elif tool_name == "search_handbook":
            return search_handbook(arguments.get("query", ""), db_path=db_path)
        else:
            return {"error": True, "message": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return {"error": True, "message": str(e)}

