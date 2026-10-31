"""
Database management for the Student Support Agent.
Handles SQLite schema creation, connections, and CRUD operations.
All queries use parameterized SQL to prevent injection.
"""

import sqlite3
import os
import logging
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_db(db_path=None):
    """Get a database connection with row factory enabled.
    
    Args:
        db_path: Optional path override for testing.
        
    Returns:
        sqlite3.Connection with Row factory.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None):
    """Initialize the database schema. Creates all required tables.
    
    Args:
        db_path: Optional path override for testing.
    """
    conn = get_db(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                programme TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS fee_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                total_fees REAL NOT NULL,
                paid_amount REAL NOT NULL DEFAULT 0,
                due_amount REAL NOT NULL,
                due_date TEXT,
                payment_status TEXT NOT NULL DEFAULT 'pending',
                last_payment_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            );
            
            CREATE TABLE IF NOT EXISTS scholarship_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                scholarship_name TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                awarded_date TEXT,
                expiry_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            );
            
            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            );
            
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE(student_id, key)
            );
            
            CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE NOT NULL,
                student_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approver_id TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT,
                resolution_notes TEXT,
                trace_id TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            );
            
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                actor_id TEXT,
                action TEXT NOT NULL,
                target_resource TEXT,
                authorization_decision TEXT,
                approval_status TEXT,
                approver_id TEXT,
                execution_status TEXT,
                outcome TEXT,
                trace_id TEXT,
                details TEXT
            );
            
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT UNIQUE NOT NULL,
                test_case_id TEXT,
                student_id TEXT,
                question TEXT,
                selected_tool TEXT,
                tool_arguments TEXT,
                tool_result TEXT,
                retrieved_evidence TEXT,
                memory_used TEXT,
                start_time TEXT,
                end_time TEXT,
                latency_ms REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                final_answer TEXT,
                success INTEGER
            );
        """)
        conn.commit()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise
    finally:
        conn.close()


# --- Student CRUD ---

def get_student(student_id, db_path=None):
    """Retrieve a student record by ID.
    
    Args:
        student_id: The student's ID.
        db_path: Optional database path.
        
    Returns:
        dict or None: Student record as dict, or None if not found.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_student(student_id, name, email, password_hash, role="student", programme=None, db_path=None):
    """Create a new student account in the database.
    
    Args:
        student_id: Unique student ID (e.g., STU004).
        name: Full student name.
        email: Student email address.
        password_hash: Securely hashed password.
        role: Account role ('student' or 'approver').
        programme: Academic programme name.
        db_path: Optional database path.
        
    Returns:
        tuple: (success: bool, message: str)
    """
    conn = get_db(db_path)
    try:
        # Check if student ID already exists
        existing_id = conn.execute(
            "SELECT student_id FROM students WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        if existing_id:
            return False, f"Student ID '{student_id}' is already registered."
        
        # Check if email already exists
        existing_email = conn.execute(
            "SELECT student_id FROM students WHERE LOWER(email) = LOWER(?)",
            (email,)
        ).fetchone()
        if existing_email:
            return False, f"Email '{email}' is already in use."
        
        # Insert student record
        conn.execute(
            """
            INSERT INTO students (student_id, name, email, password_hash, role, programme)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, name, email, password_hash, role, programme)
        )
        
        # Initialize default fee record for newly registered student
        conn.execute(
            """
            INSERT INTO fee_status (student_id, total_fees, paid_amount, due_amount, due_date, payment_status)
            VALUES (?, 12000.0, 0.0, 12000.0, '2026-12-31', 'unpaid')
            """,
            (student_id,)
        )
        
        conn.commit()
        return True, "Account registered successfully."
    except Exception as e:
        logger.error(f"Error registering student {student_id}: {e}")
        return False, f"Registration failed: {str(e)}"
    finally:
        conn.close()


def get_fee_status(student_id, db_path=None):
    """Retrieve fee status for a student.
    
    Args:
        student_id: The student's ID.
        db_path: Optional database path.
        
    Returns:
        dict or None: Fee status record, or None if not found.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM fee_status WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_scholarship_status(student_id, db_path=None):
    """Retrieve scholarship status for a student.
    
    Args:
        student_id: The student's ID.
        db_path: Optional database path.
        
    Returns:
        dict or None: Scholarship record, or None if not found.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM scholarship_status WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_support_request_record(student_id, category, description, db_path=None):
    """Create a new support request in the database.
    
    Args:
        student_id: The student's ID.
        category: Support request category.
        description: Description of the issue.
        db_path: Optional database path.
        
    Returns:
        int: The ID of the created support request.
    """
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO support_requests (student_id, category, description) VALUES (?, ?, ?)",
            (student_id, category, description)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_fee_status(student_id, updates, db_path=None):
    """Update fee status for a student.
    
    Args:
        student_id: The student's ID.
        updates: Dict of fields to update.
        db_path: Optional database path.
        
    Returns:
        bool: True if update succeeded.
    """
    allowed_fields = {"total_fees", "paid_amount", "due_amount", "due_date",
                      "payment_status", "last_payment_date"}
    
    fields = {k: v for k, v in updates.items() if k in allowed_fields}
    if not fields:
        return False
    
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [student_id]
    
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            f"UPDATE fee_status SET {set_clause} WHERE student_id = ?",
            values
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
