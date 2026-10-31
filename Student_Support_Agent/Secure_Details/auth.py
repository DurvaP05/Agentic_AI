"""
Authentication module for the Student Support Agent.
Handles password hashing, verification, and user authentication.
Uses Werkzeug's security utilities for secure password hashing.
"""

import logging
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_student, create_student

logger = logging.getLogger(__name__)


def hash_password(password):
    """Hash a password using Werkzeug's PBKDF2 (scrypt-like) hashing.
    
    Args:
        password: Plain-text password.
        
    Returns:
        str: Hashed password string.
    """
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password, password_hash):
    """Verify a password against its hash.
    
    Args:
        password: Plain-text password to verify.
        password_hash: Stored password hash.
        
    Returns:
        bool: True if the password matches.
    """
    return check_password_hash(password_hash, password)


def authenticate(student_id, password, db_path=None):
    """Authenticate a student with their ID and password.
    
    Args:
        student_id: The student's ID.
        password: The plain-text password.
        db_path: Optional database path.
        
    Returns:
        dict or None: Student record (without password_hash) if authenticated,
                      None if authentication fails.
    """
    if not student_id or not password:
        logger.warning("Authentication attempted with empty credentials.")
        return None
    
    student = get_student(student_id, db_path)
    if student is None:
        logger.warning(f"Authentication failed: student ID not found (ID masked).")
        return None
    
    if not verify_password(password, student["password_hash"]):
        logger.warning(f"Authentication failed: incorrect password for student.")
        return None
    
    # Return student info without the password hash
    safe_student = {k: v for k, v in student.items() if k != "password_hash"}
    logger.info(f"Student authenticated successfully: {student_id}")
    return safe_student


def get_user_safe(student_id, db_path=None):
    """Retrieve a student record without sensitive fields.
    
    Args:
        student_id: The student's ID.
        db_path: Optional database path.
        
    Returns:
        dict or None: Student record without password_hash, or None.
    """
    student = get_student(student_id, db_path)
    if student:
        return {k: v for k, v in student.items() if k != "password_hash"}
    return None


def register_user(student_id, name, email, password, programme=None, db_path=None):
    """Register a new student account.
    
    Args:
        student_id: The student ID (e.g., STU004).
        name: Full student name.
        email: University email address.
        password: Plain-text password.
        programme: Academic programme name.
        db_path: Optional database path.
        
    Returns:
        tuple: (success: bool, message: str)
    """
    student_id = (student_id or "").strip().upper()
    name = (name or "").strip()
    email = (email or "").strip().lower()
    
    if not student_id:
        return False, "Student ID cannot be empty."
    if len(student_id) < 3:
        return False, "Student ID must be at least 3 characters."
    if not name:
        return False, "Full Name cannot be empty."
    if not email or "@" not in email or "." not in email:
        return False, "Please enter a valid email address."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long."
        
    hashed = hash_password(password)
    return create_student(
        student_id=student_id,
        name=name,
        email=email,
        password_hash=hashed,
        role="student",
        programme=programme.strip() if programme else None,
        db_path=db_path
    )
