"""Central configuration for ParcelPilot AI."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
EXCEL_DIR = DATA_DIR / "excel"
DB_PATH = DATA_DIR / "parcelpilot.db"
CHROMA_DIR = DATA_DIR / "chroma"

# Dataset snapshot time (from README)
SNAPSHOT_TIME = "2026-08-16T11:00:00+05:30"
SNAPSHOT_TIME_IST = "2026-08-16 11:00 Asia/Kolkata"

# LLM Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")

# Embedding Config
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")

# Agent Config
MAX_TOOL_CALLS = 5
MAX_ITERATIONS = 6

# Source Authority Levels
SOURCE_AUTHORITY = {
    "customer_agreement": 1,  # Highest
    "support_policy": 2,
    "cancellation_sop": 3,
    "product_guide": 4,
    "historical_context": 5,  # Lowest - context only
}

# Collection routing
CURRENT_COLLECTION = "parcelpilot_current"
HISTORICAL_COLLECTION = "parcelpilot_historical"
