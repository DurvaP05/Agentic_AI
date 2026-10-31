"""
Database module for Assignment 1 - Intelligent Student Support Agent.
Manages SQLite storage for students, fees, scholarships, support requests, memory, and traces.
"""

import sqlite3
import os
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_db(db_path=None):
    """Get a database connection with dict-like row access."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Initialize the database schema for Assignment 1."""
    conn = get_db(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
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
                UNIQUE(student_id, key)
            );
            
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL UNIQUE,
                test_case_id TEXT,
                student_id TEXT,
                question TEXT NOT NULL,
                selected_tool TEXT,
                tool_arguments TEXT,
                tool_result TEXT,
                retrieved_evidence TEXT,
                memory_used TEXT,
                final_answer TEXT,
                latency_ms REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                start_time TEXT,
                end_time TEXT,
                success INTEGER
            );
        """)
        conn.commit()
        logger.info("Assignment 1 database schema initialized.")
    finally:
        conn.close()


def get_student(student_id, db_path=None):
    """Retrieve a student record by ID."""
    conn = get_db(db_path)
    try:
        row = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_students(db_path=None):
    """Retrieve all students for session selection."""
    conn = get_db(db_path)
    try:
        rows = conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_fee_status(student_id, db_path=None):
    """Retrieve fee status for a student."""
    conn = get_db(db_path)
    try:
        row = conn.execute("SELECT * FROM fee_status WHERE student_id = ?", (student_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_scholarship_status(student_id, db_path=None):
    """Retrieve scholarship record for a student."""
    conn = get_db(db_path)
    try:
        row = conn.execute("SELECT * FROM scholarship_status WHERE student_id = ?", (student_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_support_request_record(student_id, category, description, db_path=None):
    """Insert a new support request."""
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

