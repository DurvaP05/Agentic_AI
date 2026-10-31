"""
Authorization module for the Student Support Agent.
Implements access-control checks in deterministic application code.
These checks are enforced at the tool/function level, not just in prompts.
"""

import logging
from database import get_student

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when an access-control check fails."""
    
    def __init__(self, message="Access denied.", actor_id=None, action=None, target=None):
        self.message = message
        self.actor_id = actor_id
        self.action = action
        self.target = target
        super().__init__(self.message)


# Define which actions each role can perform
ROLE_PERMISSIONS = {
    "student": {
        "read_own_fees",
        "read_own_scholarship",
        "create_own_support_request",
        "read_own_support_requests",
        "read_handbook",
        "read_own_memory",
        "write_own_memory",
        "request_fee_correction",
        "view_own_approvals",
        "view_own_audit_logs",
    },
    "approver": {
        "read_own_fees",
        "read_own_scholarship",
        "create_own_support_request",
        "read_own_support_requests",
        "read_handbook",
        "read_own_memory",
        "write_own_memory",
        "request_fee_correction",
        "view_own_approvals",
        "view_pending_approvals",
        "approve_request",
        "reject_request",
        "view_all_audit_logs",
        "execute_approved_action",
    },
}

# Actions that require the actor to be the same as the target
OWN_RESOURCE_ACTIONS = {
    "read_own_fees",
    "read_own_scholarship",
    "create_own_support_request",
    "read_own_support_requests",
    "read_own_memory",
    "write_own_memory",
    "request_fee_correction",
    "view_own_approvals",
    "view_own_audit_logs",
}


def check_access(actor_id, action, target_student_id=None, db_path=None):
    """Check if an actor is authorized to perform an action.
    
    Args:
        actor_id: The ID of the user attempting the action.
        action: The action being attempted.
        target_student_id: The ID of the student whose data is being accessed.
        db_path: Optional database path.
        
    Returns:
        bool: True if access is allowed, False otherwise.
    """
    if not actor_id:
        logger.warning(f"Authorization check failed: no actor_id provided for action '{action}'.")
        return False
    
    # Get the actor's role
    actor = get_student(actor_id, db_path)
    if actor is None:
        logger.warning(f"Authorization check failed: actor not found.")
        return False
    
    role = actor.get("role", "student")
    permissions = ROLE_PERMISSIONS.get(role, set())
    
    # Check if the role has the required permission
    if action not in permissions:
        logger.warning(
            f"Authorization denied: role '{role}' lacks permission '{action}'."
        )
        return False
    
    # For own-resource actions, verify actor == target
    if action in OWN_RESOURCE_ACTIONS:
        if target_student_id and target_student_id != actor_id:
            logger.warning(
                f"Authorization denied: actor cannot access another student's data."
            )
            return False
    
    return True


def require_access(actor_id, action, target_student_id=None, db_path=None):
    """Require authorization, raising AuthorizationError if denied.
    
    Args:
        actor_id: The ID of the user attempting the action.
        action: The action being attempted.
        target_student_id: The student whose data is being accessed.
        db_path: Optional database path.
        
    Raises:
        AuthorizationError: If access is denied.
    """
    if not check_access(actor_id, action, target_student_id, db_path):
        error = AuthorizationError(
            message=f"Access denied: You are not authorized to perform '{action}'"
                    + (f" on another student's record." if target_student_id and target_student_id != actor_id
                       else "."),
            actor_id=actor_id,
            action=action,
            target=target_student_id
        )
        # Log the authorization failure (without sensitive details)
        logger.warning(f"AuthorizationError: action='{action}', denied.")
        raise error


def is_approver(actor_id, db_path=None):
    """Check if a user has the approver role.
    
    Args:
        actor_id: The user's ID.
        db_path: Optional database path.
        
    Returns:
        bool: True if the user is an approver.
    """
    actor = get_student(actor_id, db_path)
    if actor is None:
        return False
    return actor.get("role") == "approver"


def require_authentication(actor_id):
    """Require that a user is authenticated.
    
    Args:
        actor_id: The user's ID (None if not authenticated).
        
    Raises:
        AuthorizationError: If the user is not authenticated.
    """
    if not actor_id:
        raise AuthorizationError(
            message="Authentication required. Please log in to access this feature.",
            actor_id=None,
            action="authentication",
            target=None
        )
