import os
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
load_dotenv()

# --- Project Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = Path.home() / ".code_intel_store"
VAULT_DIR = VAULT_ROOT / "db"
LOG_DIR = VAULT_ROOT / "logs"

# Ensure directories exist
for d in [VAULT_DIR, LOG_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local
        d = PROJECT_ROOT / ".code_intel_store" / d.name
        d.mkdir(parents=True, exist_ok=True)

# Cache Directory (Shared global cache)
CACHE_DIR = VAULT_ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB_PATH = CACHE_DIR / "embeddings.sqlite"

# --- Embedding Configuration ---
# bge-m3 is the architectural standard for this project
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3:latest")
EMBEDDING_ENDPOINT = os.getenv("EMBEDDING_ENDPOINT", "http://localhost:11434/api/embeddings")

try:
    EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
except ValueError:
    EMBEDDING_DIMENSIONS = 1024

# --- Parsing Configuration ---
SUPPORTED_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", 
    ".md", ".json", ".sql", ".go", ".rs", ".java", ".cpp", ".c", ".h",
    ".yaml", ".yml", ".toml", ".dart", ".rules"
}

IGNORE_DIRS: Set[str] = {
    "node_modules", "venv", ".venv", "env", ".env", "__pycache__", ".git", 
    "build", "dist", ".idea", ".vscode", "coverage", ".pytest_cache",
    ".cognee_vault", "logs", ".dart_tool", "ephemeral"
}

# --- Database Configuration ---
LANCEDB_URI = str(VAULT_DIR)
TABLE_NAME = "chunks"
