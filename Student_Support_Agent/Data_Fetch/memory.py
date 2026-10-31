"""
Persistent memory module for the Student Support Agent.
Stores user-scoped, non-sensitive preferences and context.
Filters out sensitive information before persistence.
"""

import re
import logging
from database import get_db

logger = logging.getLogger(__name__)

# Patterns that indicate sensitive information - NEVER persist these
SENSITIVE_PATTERNS = [
    re.compile(r'\b(?:password|passwd|pwd)\b.*[:=]\s*\S+', re.IGNORECASE),
    re.compile(r'\b(?:otp|one.time.password|verification.code)\b.*[:=]?\s*\d{4,8}', re.IGNORECASE),
    re.compile(r'\b\d{4,8}\b.*\b(?:otp|one.time.password|verification.code)\b', re.IGNORECASE),
    re.compile(r'\bmy\s+(?:password|otp|pin|code)\s+is\s+\S+', re.IGNORECASE),
    re.compile(r'\b(?:api[_\s]?key|secret[_\s]?key|access[_\s]?token|auth[_\s]?token)\b.*[:=]\s*\S+', re.IGNORECASE),
    re.compile(r'\b(?:session[_\s]?token|jwt|bearer)\b.*[:=]?\s*\S+', re.IGNORECASE),
    re.compile(r'\b(?:credit.card|card.number|cvv|expir)\b', re.IGNORECASE),
    re.compile(r'\b\d{13,19}\b', re.IGNORECASE),  # Credit card-like numbers
    re.compile(r'\b(?:ssn|social.security)\b', re.IGNORECASE),
    re.compile(r'\bpassword\s*[:=]\s*\S+', re.IGNORECASE),
    re.compile(r'gsk_[a-zA-Z0-9]{20,}', re.IGNORECASE),  # Groq API key pattern
    re.compile(r'sk-[a-zA-Z0-9_-]{20,}', re.IGNORECASE),    # OpenAI-like API key pattern
]

# Keys that should never be stored in memory
SENSITIVE_KEYS = {
    "password", "passwd", "pwd", "otp", "pin", "token", "secret",
    "api_key", "apikey", "access_token", "session_token", "credit_card",
    "card_number", "cvv", "ssn", "social_security",
}


def is_sensitive(text):
    """Check if text contains sensitive information.
    
    Args:
        text: Text to check.
        
    Returns:
        bool: True if the text contains sensitive patterns.
    """
    if not text:
        return False
    
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(str(text)):
            return True
    return False


def is_sensitive_key(key):
    """Check if a memory key represents sensitive information.
    
    Args:
        key: The memory key to check.
        
    Returns:
        bool: True if the key is sensitive.
    """
    return key.lower().strip() in SENSITIVE_KEYS


def save_memory(student_id, key, value, db_path=None):
    """Save a memory entry for a student, filtering sensitive data.
    
    Args:
        student_id: The student's ID.
        key: Memory key (e.g., 'preferred_language', 'programme').
        value: Memory value.
        db_path: Optional database path.
        
    Returns:
        bool: True if saved successfully, False if rejected as sensitive.
    """
    # Check for sensitive keys
    if is_sensitive_key(key):
        logger.warning(f"Rejected sensitive memory key: '{key}' (value not logged)")
        return False
    
    # Check for sensitive values
    if is_sensitive(value):
        logger.warning(f"Rejected sensitive memory value for key: '{key}'")
        return False
    
    conn = get_db(db_path)
    try:
        conn.execute(
            """INSERT INTO memory (student_id, key, value) 
               VALUES (?, ?, ?)
               ON CONFLICT(student_id, key) 
               DO UPDATE SET value = excluded.value, updated_at = datetime('now')""",
            (student_id, key, str(value))
        )
        conn.commit()
        logger.info(f"Memory saved for student: key='{key}'")
        return True
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")
        return False
    finally:
        conn.close()


def get_memories(student_id, db_path=None):
    """Retrieve all memory entries for a student.
    
    Args:
        student_id: The student's ID.
        db_path: Optional database path.
        
    Returns:
        list[dict]: List of memory records.
    """
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            "SELECT key, value, updated_at FROM memory WHERE student_id = ? ORDER BY updated_at DESC",
            (student_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_memory(student_id, key, db_path=None):
    """Retrieve a specific memory entry for a student.
    
    Args:
        student_id: The student's ID.
        key: The memory key.
        db_path: Optional database path.
        
    Returns:
        str or None: The memory value, or None if not found.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM memory WHERE student_id = ? AND key = ?",
            (student_id, key)
        ).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def update_memory(student_id, key, value, db_path=None):
    """Update an existing memory entry.
    
    Args:
        student_id: The student's ID.
        key: The memory key.
        value: The new value.
        db_path: Optional database path.
        
    Returns:
        bool: True if updated successfully.
    """
    # Reject sensitive data
    if is_sensitive_key(key) or is_sensitive(value):
        logger.warning(f"Rejected sensitive memory update for key: '{key}'")
        return False
    
    return save_memory(student_id, key, value, db_path)


def delete_memory(student_id, key, db_path=None):
    """Delete a memory entry for a student.
    
    Args:
        student_id: The student's ID.
        key: The memory key to delete.
        db_path: Optional database path.
        
    Returns:
        bool: True if deleted successfully.
    """
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "DELETE FROM memory WHERE student_id = ? AND key = ?",
            (student_id, key)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
