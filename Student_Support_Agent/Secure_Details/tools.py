"""
Tool definitions and implementations for the Student Support Agent.
Each tool has a clear schema, validates arguments, enforces authorization,
and returns structured results.
"""

import json
import logging
from database import get_fee_status, get_scholarship_status, create_support_request_record
from authorization import require_access, require_authentication, AuthorizationError
from retrieval import HandbookRetriever
from audit import log_audit_event

logger = logging.getLogger(__name__)

# Singleton retriever - initialized on first use
_retriever = None


def _get_retriever():
    """Get or create the singleton handbook retriever."""
    global _retriever
    if _retriever is None:
        _retriever = HandbookRetriever()
    return _retriever


# --- Groq Tool/Function Calling Definitions ---
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_fee_status",
            "description": "Retrieves the authenticated student's fee status including total fees, paid amount, due amount, payment status, and due date. Only the student's own fee record can be accessed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID to look up. Must match the authenticated student's ID."
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
            "description": "Retrieves the authenticated student's scholarship status including scholarship name, amount, status, and dates. Only the student's own scholarship record can be accessed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID to look up. Must match the authenticated student's ID."
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
            "description": "Creates a new support ticket for the authenticated student. Categories include: academic, financial, technical, administrative, wellbeing, general.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID creating the request. Must match the authenticated student's ID."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["academic", "financial", "technical", "administrative", "wellbeing", "general"],
                        "description": "Category of the support request."
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
            "description": "Retrieves relevant course-change guidance and policies from the student handbook. Use this when a student asks about changing courses, adding/dropping courses, or programme changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The specific question about course changes to search for in the handbook."
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
            "description": "Searches the student handbook for academic calendar dates, session start dates, semester schedules, deadlines, fee and scholarship policies, course change rules, support procedures, and institutional rules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant handbook policies or dates."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_fee_correction",
            "description": "Submits a request to correct an error in the student's fee record. This is a sensitive action that requires approval by a finance administrator before any changes are made.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student ID requesting the correction. Must match the authenticated student's ID."
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the fee error and the expected correction."
                    }
                },
                "required": ["student_id", "description"]
            }
        }
    }
]


def check_fee_status(student_id, actor_id, db_path=None):
    """Retrieve fee status for the authenticated student.
    
    Args:
        student_id: Student ID to query (must match actor_id).
        actor_id: Authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Fee status or error information.
    """
    try:
        require_authentication(actor_id)
        # Override student_id with actor_id to prevent identity spoofing
        student_id = actor_id
        require_access(actor_id, "read_own_fees", student_id, db_path)
    except AuthorizationError as e:
        log_audit_event(
            actor_id=actor_id or "anonymous",
            action="check_fee_status",
            target_resource=f"fee_status:{student_id}",
            authorization_decision="denied",
            execution_status="blocked",
            outcome=str(e.message),
            db_path=db_path
        )
        return {"error": True, "message": e.message}
    
    fee = get_fee_status(student_id, db_path)
    
    if fee is None:
        log_audit_event(
            actor_id=actor_id,
            action="check_fee_status",
            target_resource=f"fee_status:{student_id}",
            authorization_decision="allowed",
            execution_status="success",
            outcome="No fee record found",
            db_path=db_path
        )
        return {"error": False, "message": "No fee record found for your account.", "data": None}
    
    log_audit_event(
        actor_id=actor_id,
        action="check_fee_status",
        target_resource=f"fee_status:{student_id}",
        authorization_decision="allowed",
        execution_status="success",
        outcome="Fee status retrieved",
        db_path=db_path
    )
    
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


def check_scholarship_status(student_id, actor_id, db_path=None):
    """Retrieve scholarship status for the authenticated student.
    
    Args:
        student_id: Student ID to query (must match actor_id).
        actor_id: Authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Scholarship status or error information.
    """
    try:
        require_authentication(actor_id)
        student_id = actor_id
        require_access(actor_id, "read_own_scholarship", student_id, db_path)
    except AuthorizationError as e:
        log_audit_event(
            actor_id=actor_id or "anonymous",
            action="check_scholarship_status",
            target_resource=f"scholarship:{student_id}",
            authorization_decision="denied",
            execution_status="blocked",
            outcome=str(e.message),
            db_path=db_path
        )
        return {"error": True, "message": e.message}
    
    scholarship = get_scholarship_status(student_id, db_path)
    
    if scholarship is None:
        log_audit_event(
            actor_id=actor_id,
            action="check_scholarship_status",
            target_resource=f"scholarship:{student_id}",
            authorization_decision="allowed",
            execution_status="success",
            outcome="No scholarship record found",
            db_path=db_path
        )
        return {"error": False, "message": "No scholarship record found for your account.", "data": None}
    
    log_audit_event(
        actor_id=actor_id,
        action="check_scholarship_status",
        target_resource=f"scholarship:{student_id}",
        authorization_decision="allowed",
        execution_status="success",
        outcome="Scholarship status retrieved",
        db_path=db_path
    )
    
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


def create_support_request(student_id, category, description, actor_id, db_path=None):
    """Create a new support request for the authenticated student.
    
    Args:
        student_id: Student ID creating the request (must match actor_id).
        category: Category of the request.
        description: Description of the issue.
        actor_id: Authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Support request details or error.
    """
    try:
        require_authentication(actor_id)
        student_id = actor_id
        require_access(actor_id, "create_own_support_request", student_id, db_path)
    except AuthorizationError as e:
        log_audit_event(
            actor_id=actor_id or "anonymous",
            action="create_support_request",
            target_resource=f"support_request:{student_id}",
            authorization_decision="denied",
            execution_status="blocked",
            outcome=str(e.message),
            db_path=db_path
        )
        return {"error": True, "message": e.message}
    
    # Validate category
    valid_categories = {"academic", "financial", "technical", "administrative", "wellbeing", "general"}
    if category.lower() not in valid_categories:
        return {
            "error": True,
            "message": f"Invalid category. Valid categories: {', '.join(sorted(valid_categories))}"
        }
    
    # Validate description
    if not description or len(description.strip()) < 10:
        return {"error": True, "message": "Description must be at least 10 characters long."}
    
    try:
        request_id = create_support_request_record(student_id, category.lower(), description, db_path)
        
        log_audit_event(
            actor_id=actor_id,
            action="create_support_request",
            target_resource=f"support_request:{request_id}",
            authorization_decision="allowed",
            execution_status="success",
            outcome=f"Support request #{request_id} created",
            db_path=db_path
        )
        
        return {
            "error": False,
            "message": f"Support request #{request_id} created successfully.",
            "data": {
                "request_id": request_id,
                "student_id": student_id,
                "category": category.lower(),
                "status": "open"
            }
        }
    except Exception as e:
        logger.error(f"Failed to create support request: {e}")
        return {"error": True, "message": "Failed to create support request. Please try again later."}


def get_course_change_information(query="course change", actor_id=None, db_path=None):
    """Retrieve course-change guidance from the student handbook.
    
    Args:
        query: Specific course change question.
        actor_id: Optional authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Relevant handbook information.
    """
    retriever = _get_retriever()
    search_query = f"course change {query}"
    results = retriever.retrieve(search_query, top_k=3)
    
    if not results:
        return {
            "error": False,
            "message": "No specific course change information found in the handbook. "
                      "Please contact the Academic Advising Office for detailed guidance.",
            "data": None,
            "source": "student_handbook"
        }
    
    return {
        "error": False,
        "message": "Course change information retrieved from the student handbook.",
        "data": [{"section": r["section"], "content": r["text"], "relevance": r["score"]} for r in results],
        "source": "student_handbook"
    }


def search_handbook(query, actor_id=None, db_path=None):
    """Search the student handbook for relevant policies.
    
    Args:
        query: Search query.
        actor_id: Optional authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Relevant handbook sections.
    """
    retriever = _get_retriever()
    results = retriever.retrieve(query, top_k=5)
    
    if not results:
        return {
            "error": False,
            "message": "The available student handbook does not contain enough information "
                      "to answer this question. Please contact the appropriate institutional "
                      "office for assistance.",
            "data": None,
            "source": "student_handbook"
        }
    
    return {
        "error": False,
        "message": "Relevant policies found in the student handbook.",
        "data": [{"section": r["section"], "content": r["text"], "relevance": r["score"]} for r in results],
        "source": "student_handbook"
    }


def request_fee_correction(student_id, description, actor_id, db_path=None):
    """Request a fee record correction (sensitive action requiring approval).
    
    Args:
        student_id: Student ID requesting correction (must match actor_id).
        description: Description of the fee error.
        actor_id: Authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Approval request details or error.
    """
    # Import here to avoid circular imports
    from approval import create_approval_request
    
    try:
        require_authentication(actor_id)
        student_id = actor_id
        require_access(actor_id, "request_fee_correction", student_id, db_path)
    except AuthorizationError as e:
        log_audit_event(
            actor_id=actor_id or "anonymous",
            action="request_fee_correction",
            target_resource=f"fee_status:{student_id}",
            authorization_decision="denied",
            execution_status="blocked",
            outcome=str(e.message),
            db_path=db_path
        )
        return {"error": True, "message": e.message}
    
    if not description or len(description.strip()) < 10:
        return {"error": True, "message": "Please provide a detailed description of the fee error (at least 10 characters)."}
    
    try:
        action_details = {
            "student_id": student_id,
            "correction_description": description,
            "target_table": "fee_status"
        }
        
        request_id = create_approval_request(
            student_id=student_id,
            action_type="fee_correction",
            action_details=action_details,
            db_path=db_path
        )
        
        log_audit_event(
            actor_id=actor_id,
            action="request_fee_correction",
            target_resource=f"fee_status:{student_id}",
            authorization_decision="allowed",
            approval_status="pending",
            execution_status="pending",
            outcome=f"Approval request {request_id} created",
            db_path=db_path
        )
        
        return {
            "error": False,
            "message": f"Fee correction request submitted successfully. "
                      f"Request ID: {request_id}. "
                      f"This request requires approval by a finance administrator before any changes are made. "
                      f"You will be notified when a decision is made.",
            "data": {
                "request_id": request_id,
                "status": "pending",
                "action_type": "fee_correction"
            }
        }
    except Exception as e:
        logger.error(f"Failed to create fee correction request: {e}")
        return {"error": True, "message": "Failed to submit fee correction request. Please try again later."}


def execute_tool(tool_name, arguments, actor_id, db_path=None):
    """Route and execute a tool call with validation and authorization.
    
    Args:
        tool_name: Name of the tool to execute.
        arguments: Dict of tool arguments.
        actor_id: Authenticated user's ID.
        db_path: Optional database path.
        
    Returns:
        dict: Tool execution result.
    """
    # Validate tool name
    valid_tools = {
        "check_fee_status", "check_scholarship_status",
        "create_support_request", "get_course_change_information",
        "search_handbook", "request_fee_correction"
    }
    
    if tool_name not in valid_tools:
        logger.warning(f"Unknown tool requested: {tool_name}")
        return {"error": True, "message": f"Unknown tool: {tool_name}"}
    
    # Validate arguments
    if not isinstance(arguments, dict):
        try:
            arguments = json.loads(arguments) if isinstance(arguments, str) else {}
        except (json.JSONDecodeError, TypeError):
            return {"error": True, "message": "Invalid tool arguments format."}
    
    try:
        if tool_name == "check_fee_status":
            return check_fee_status(
                student_id=arguments.get("student_id", ""),
                actor_id=actor_id,
                db_path=db_path
            )
        
        elif tool_name == "check_scholarship_status":
            return check_scholarship_status(
                student_id=arguments.get("student_id", ""),
                actor_id=actor_id,
                db_path=db_path
            )
        
        elif tool_name == "create_support_request":
            return create_support_request(
                student_id=arguments.get("student_id", ""),
                category=arguments.get("category", "general"),
                description=arguments.get("description", ""),
                actor_id=actor_id,
                db_path=db_path
            )
        
        elif tool_name == "get_course_change_information":
            return get_course_change_information(
                query=arguments.get("query", "course change"),
                actor_id=actor_id,
                db_path=db_path
            )
        
        elif tool_name == "search_handbook":
            return search_handbook(
                query=arguments.get("query", ""),
                actor_id=actor_id,
                db_path=db_path
            )
        
        elif tool_name == "request_fee_correction":
            return request_fee_correction(
                student_id=arguments.get("student_id", ""),
                description=arguments.get("description", ""),
                actor_id=actor_id,
                db_path=db_path
            )
    
    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return {"error": True, "message": f"An error occurred while executing {tool_name}. Please try again later."}
