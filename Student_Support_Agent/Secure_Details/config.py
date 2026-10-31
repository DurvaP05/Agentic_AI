"""
Configuration management for the Student Support Agent.
Loads environment variables and validates required settings.
"""

import os
import sys
from dotenv import load_dotenv


# Load .env file
load_dotenv()

# --- Configuration Constants ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "student_support.db"))
HANDBOOK_PATH = os.getenv("HANDBOOK_PATH", os.path.join(BASE_DIR, "data", "student_handbook.md"))

# Agent configuration
MAX_TOOL_CALLS = 5  # Safeguard against repeated tool calls
MAX_RETRIES = 2     # Retries for Groq API errors
REQUEST_TIMEOUT = 30  # Seconds


def validate_config():
    """Validate that all required configuration is present.
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not GROQ_API_KEY or GROQ_API_KEY in ("your_groq_api_key_here", "Your api_key"):
        return False, (
            "GROQ_API_KEY is not configured. "
            "Please create a .env file with your Groq API key. "
            "See .env.example for the required format."
        )
    
    if not GROQ_MODEL:
        return False, (
            "GROQ_MODEL is not configured. "
            "Set GROQ_MODEL in your .env file (e.g., qwen/qwen3.8-27b)."
        )
    
    return True, None


def get_groq_client():
    """Create and return a configured Groq client.
    
    Returns:
        groq.Groq: Configured Groq client.
        
    Raises:
        SystemExit: If GROQ_API_KEY is not configured.
    """
    is_valid, error = validate_config()
    if not is_valid:
        print(f"Configuration Error: {error}", file=sys.stderr)
        raise SystemExit(error)
    
    import groq
    return groq.Groq(api_key=GROQ_API_KEY)
