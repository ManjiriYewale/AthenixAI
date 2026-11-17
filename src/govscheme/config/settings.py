
"""Environment-driven settings (no secrets in code)."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
ROOT = Path(__file__).resolve().parents[3]

# Load environment variables from project root
load_dotenv(ROOT / ".env")

# Database configuration
DB_PATH = Path(os.getenv("ATHENIX_DB", ROOT / "storage" / "athenix.db"))

# Initial scheme dataset
SEED_PATH = Path(os.getenv("ATHENIX_SEED", ROOT / "data" / "samples" / "demo_schemes.json"))

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.groq.com/openai/v1"
)
LLM_MODEL = os.getenv("LLM_MODEL", "")

# Government scheme PDF directories
DOC_DIRS = [
    ROOT / "documents",
    ROOT / "data" / "samples" / "docs"
]
