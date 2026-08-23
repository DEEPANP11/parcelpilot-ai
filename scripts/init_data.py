"""Startup script to initialize all data."""
import sys
sys.path.insert(0, ".")

from pathlib import Path
from config.settings import DATA_DIR, CHROMA_DIR

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
print("Initializing database...")
from app.data.database import init_db
init_db()

# Ingest Excel data
print("Ingesting Excel data...")
from app.data.ingest_excel import run_ingestion
run_ingestion()

# Ingest documents into ChromaDB
print("Ingesting documents into ChromaDB...")
from app.rag.ingest_documents import ingest_documents
ingest_documents()

print("Initialization complete!")
