"""
Audit logging module for the Student Support Agent.
Records all important operations with append-only audit trail.
Never stores passwords, OTPs, API keys, or other secrets.
"""

import uuid
import logging
from datetime import datetime
from database import get_db
from memory import is_sensitive

logger = logging.getLogger(__name__)

# Fields that should be masked in audit views
MASKED_FIELDS = {"password", "password_hash", "otp", "token", "api_key", "secret"}


def log_audit_event(actor_id, action, target_resource, authorization_decision,
                    approval_status=None, approver_id=None,
                    execution_status="success", outcome="",
                    trace_id=None, details="", db_path=None):
    """Record an audit event in the persistent audit log.
    
    Args:
        actor_id: The user performing the action.
        action: The action being performed.
        target_resource: The resource being acted upon.
        authorization_decision: 'allowed', 'denied', or 'pending'.
        approval_status: Optional approval status.
        approver_id: Optional approver ID.
        execution_status: 'success', 'failure', 'pending', 'blocked'.
        outcome: Description of the outcome.
        trace_id: Optional associated trace ID.
        details: Additional non-sensitive details.
        db_path: Optional database path.
        
    Returns:
        str: The unique event ID.
    """
    event_id = str(uuid.uuid4())
    
    # Sanitize details to prevent sensitive data in audit logs
    safe_details = _sanitize_for_audit(details)
    safe_outcome = _sanitize_for_audit(outcome)
    
    conn = get_db(db_path)
    try:
        conn.execute(
            """INSERT INTO audit_log 
               (event_id, actor_id, action, target_resource, authorization_decision,
                approval_status, approver_id, execution_status, outcome, trace_id, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, actor_id, action, target_resource, authorization_decision,
             approval_status, approver_id, execution_status, safe_outcome,
             trace_id, safe_details)
        )
        conn.commit()
        logger.info(f"Audit event recorded: {event_id} - {action}")
        return event_id
    except Exception as e:
        logger.error(f"Failed to record audit event: {e}")
        return None
    finally:
        conn.close()


def get_audit_logs(actor_id=None, action=None, limit=100, db_path=None):
    """Retrieve audit log entries with optional filters.
    
    Args:
        actor_id: Filter by actor ID.
        action: Filter by action type.
        limit: Maximum records to return.
        db_path: Optional database path.
        
    Returns:
        list[dict]: Audit log entries with sensitive fields masked.
    """
    conn = get_db(db_path)
    try:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if actor_id:
            query += " AND actor_id = ?"
            params.append(actor_id)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        return [mask_sensitive_fields(dict(row)) for row in rows]
    finally:
        conn.close()


def mask_sensitive_fields(record):
    """Mask sensitive fields in an audit record for display.
    
    Args:
        record: Dict of audit record fields.
        
    Returns:
        dict: Record with sensitive values masked.
    """
    masked = dict(record)
    for key in masked:
        if key.lower() in MASKED_FIELDS:
            masked[key] = "***MASKED***"
        elif isinstance(masked[key], str) and is_sensitive(masked[key]):
            masked[key] = "***CONTAINS_SENSITIVE_DATA***"
    return masked


def _sanitize_for_audit(text):
    """Remove sensitive data from text before storing in audit log.
    
    Args:
        text: Text to sanitize.
        
    Returns:
        str: Sanitized text.
    """
    if not text:
        return ""
    
    if is_sensitive(str(text)):
        return "[REDACTED - contained sensitive data]"
    
    return str(text)
