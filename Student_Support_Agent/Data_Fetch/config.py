"""
Configuration management for Assignment 1 - Intelligent Student Support Agent.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env file
load_dotenv(os.path.join(BASE_DIR, ".env"))

# --- Configuration Constants ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "student_support.db"))
HANDBOOK_PATH = os.getenv("HANDBOOK_PATH", os.path.join(BASE_DIR, "data", "student_handbook.md"))

# Agent loop safeguards
MAX_TOOL_CALLS = 5
MAX_RETRIES = 2
REQUEST_TIMEOUT = 30


def validate_config():
    """Validate that required configuration is present."""
    if not GROQ_API_KEY or GROQ_API_KEY in ("your_groq_api_key_here", "Your api_key"):
        return False, "GROQ_API_KEY is not configured in .env file (currently set to placeholder)."
    if not GROQ_MODEL:
        return False, "GROQ_MODEL is not configured in .env file."
    return True, None


def get_groq_client():
    """Create and return a configured Groq client."""
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY, timeout=REQUEST_TIMEOUT)

