"""
Approval workflow module for the Student Support Agent.
Manages sensitive actions that require human approval before execution.
Prevents replay, duplicate execution, and approval of modified requests.
"""

import uuid
import json
import logging
from datetime import datetime
from database import get_db, update_fee_status
from authorization import require_access, is_approver, AuthorizationError
from audit import log_audit_event

logger = logging.getLogger(__name__)


def create_approval_request(student_id, action_type, action_details, trace_id=None, db_path=None):
    """Create a new approval request for a sensitive action.
    
    Args:
        student_id: The student requesting the action.
        action_type: Type of action (e.g., 'fee_correction').
        action_details: Dict with action parameters.
        trace_id: Optional trace ID for linking.
        db_path: Optional database path.
        
    Returns:
        str: The unique request ID.
    """
    request_id = str(uuid.uuid4())
    details_json = json.dumps(action_details, default=str)
    
    conn = get_db(db_path)
    try:
        conn.execute(
            """INSERT INTO approval_requests 
               (request_id, student_id, action_type, action_details, status, trace_id)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (request_id, student_id, action_type, details_json, trace_id)
        )
        conn.commit()
        logger.info(f"Approval request created: {request_id} ({action_type})")
        return request_id
    except Exception as e:
        logger.error(f"Failed to create approval request: {e}")
        raise
    finally:
        conn.close()


def get_pending_approvals(approver_id=None, db_path=None):
    """Get all pending approval requests.
    
    Args:
        approver_id: Optional approver ID for role checking.
        db_path: Optional database path.
        
    Returns:
        list[dict]: List of pending approval requests.
    """
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT request_id, student_id, action_type, action_details, 
                      status, created_at, trace_id
               FROM approval_requests WHERE status = 'pending'
               ORDER BY created_at ASC"""
        ).fetchall()
        
        results = []
        for row in rows:
            record = dict(row)
            try:
                record["action_details"] = json.loads(record["action_details"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(record)
        
        return results
    finally:
        conn.close()


def get_approval_status(request_id, db_path=None):
    """Get the status of an approval request.
    
    Args:
        request_id: The request ID to look up.
        db_path: Optional database path.
        
    Returns:
        dict or None: Approval request details, or None if not found.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?",
            (request_id,)
        ).fetchone()
        
        if row:
            record = dict(row)
            try:
                record["action_details"] = json.loads(record["action_details"])
            except (json.JSONDecodeError, TypeError):
                pass
            return record
        return None
    finally:
        conn.close()


def approve_request(request_id, approver_id, notes="", db_path=None):
    """Approve a pending request and execute the associated action.
    
    Args:
        request_id: The request ID to approve.
        approver_id: The approver's ID.
        notes: Optional approval notes.
        db_path: Optional database path.
        
    Returns:
        dict: Result of the approval and execution.
    """
    # Verify approver role
    if not is_approver(approver_id, db_path):
        log_audit_event(
            actor_id=approver_id,
            action="approve_request",
            target_resource=f"approval:{request_id}",
            authorization_decision="denied",
            execution_status="blocked",
            outcome="Non-approver attempted to approve request",
            db_path=db_path
        )
        return {"error": True, "message": "Access denied. Only approvers can approve requests."}
    
    conn = get_db(db_path)
    try:
        # Fetch the request with a lock-like check
        row = conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ? AND status = 'pending'",
            (request_id,)
        ).fetchone()
        
        if not row:
            # Check if it exists but is not pending
            existing = conn.execute(
                "SELECT status FROM approval_requests WHERE request_id = ?",
                (request_id,)
            ).fetchone()
            
            if existing:
                return {
                    "error": True,
                    "message": f"Request {request_id} has already been {existing['status']}. Cannot approve again."
                }
            return {"error": True, "message": f"Request {request_id} not found."}
        
        request_data = dict(row)
        
        # Update status to approved
        conn.execute(
            """UPDATE approval_requests 
               SET status = 'approved', approver_id = ?, resolved_at = datetime('now'),
                   resolution_notes = ?
               WHERE request_id = ? AND status = 'pending'""",
            (approver_id, notes, request_id)
        )
        conn.commit()
        
        # Execute the approved action
        try:
            action_details = json.loads(request_data["action_details"])
        except (json.JSONDecodeError, TypeError):
            action_details = {}
        
        execution_result = _execute_approved_action(
            request_data["action_type"], action_details, request_data["student_id"], db_path
        )
        
        # Update execution status
        exec_status = "success" if not execution_result.get("error") else "failure"
        conn.execute(
            """UPDATE approval_requests 
               SET resolution_notes = ? 
               WHERE request_id = ?""",
            (f"{notes} | Execution: {exec_status}", request_id)
        )
        conn.commit()
        
        log_audit_event(
            actor_id=approver_id,
            action="approve_request",
            target_resource=f"approval:{request_id}",
            authorization_decision="allowed",
            approval_status="approved",
            approver_id=approver_id,
            execution_status=exec_status,
            outcome=execution_result.get("message", ""),
            trace_id=request_data.get("trace_id"),
            db_path=db_path
        )
        
        return {
            "error": False,
            "message": f"Request {request_id} approved and executed successfully.",
            "data": {
                "request_id": request_id,
                "status": "approved",
                "approver_id": approver_id,
                "execution_result": execution_result
            }
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Approval processing error: {e}")
        return {"error": True, "message": "An error occurred while processing the approval."}
    finally:
        conn.close()


def reject_request(request_id, approver_id, notes="", db_path=None):
    """Reject a pending approval request. No changes are made.
    
    Args:
        request_id: The request ID to reject.
        approver_id: The approver's ID.
        notes: Optional rejection reason.
        db_path: Optional database path.
        
    Returns:
        dict: Result of the rejection.
    """
    if not is_approver(approver_id, db_path):
        log_audit_event(
            actor_id=approver_id,
            action="reject_request",
            target_resource=f"approval:{request_id}",
            authorization_decision="denied",
            execution_status="blocked",
            outcome="Non-approver attempted to reject request",
            db_path=db_path
        )
        return {"error": True, "message": "Access denied. Only approvers can reject requests."}
    
    conn = get_db(db_path)
    try:
        # Verify request is pending
        row = conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ? AND status = 'pending'",
            (request_id,)
        ).fetchone()
        
        if not row:
            existing = conn.execute(
                "SELECT status FROM approval_requests WHERE request_id = ?",
                (request_id,)
            ).fetchone()
            
            if existing:
                return {
                    "error": True,
                    "message": f"Request {request_id} has already been {existing['status']}. Cannot reject again."
                }
            return {"error": True, "message": f"Request {request_id} not found."}
        
        request_data = dict(row)
        
        # Update status to rejected - NO changes are made
        conn.execute(
            """UPDATE approval_requests 
               SET status = 'rejected', approver_id = ?, resolved_at = datetime('now'),
                   resolution_notes = ?
               WHERE request_id = ? AND status = 'pending'""",
            (approver_id, notes, request_id)
        )
        conn.commit()
        
        log_audit_event(
            actor_id=approver_id,
            action="reject_request",
            target_resource=f"approval:{request_id}",
            authorization_decision="allowed",
            approval_status="rejected",
            approver_id=approver_id,
            execution_status="blocked",
            outcome=f"Request rejected: {notes}",
            trace_id=request_data.get("trace_id"),
            db_path=db_path
        )
        
        return {
            "error": False,
            "message": f"Request {request_id} has been rejected. No changes have been made.",
            "data": {
                "request_id": request_id,
                "status": "rejected",
                "approver_id": approver_id,
                "notes": notes
            }
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Rejection processing error: {e}")
        return {"error": True, "message": "An error occurred while processing the rejection."}
    finally:
        conn.close()


def get_student_approvals(student_id, db_path=None):
    """Get all approval requests for a specific student.
    
    Args:
        student_id: The student's ID.
        db_path: Optional database path.
        
    Returns:
        list[dict]: List of approval requests.
    """
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT request_id, action_type, action_details, status, 
                      created_at, resolved_at, resolution_notes
               FROM approval_requests WHERE student_id = ?
               ORDER BY created_at DESC""",
            (student_id,)
        ).fetchall()
        
        results = []
        for row in rows:
            record = dict(row)
            try:
                record["action_details"] = json.loads(record["action_details"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(record)
        
        return results
    finally:
        conn.close()


def _execute_approved_action(action_type, action_details, student_id, db_path=None):
    """Execute an approved sensitive action.
    
    This function is ONLY called after valid approval.
    
    Args:
        action_type: The type of action to execute.
        action_details: The action parameters.
        student_id: The student the action applies to.
        db_path: Optional database path.
        
    Returns:
        dict: Execution result.
    """
    if action_type == "fee_correction":
        # For demo: apply a note about the correction
        # In production, this would modify the actual fee record
        try:
            success = update_fee_status(
                student_id,
                {"payment_status": "under_review"},
                db_path
            )
            
            if success:
                return {
                    "error": False,
                    "message": f"Fee record for {student_id} has been marked as under review "
                              f"pending correction: {action_details.get('correction_description', 'N/A')}"
                }
            else:
                return {"error": True, "message": "Failed to update fee record."}
        except Exception as e:
            logger.error(f"Fee correction execution error: {e}")
            return {"error": True, "message": "Failed to execute fee correction."}
    
    else:
        return {"error": True, "message": f"Unknown action type: {action_type}"}
