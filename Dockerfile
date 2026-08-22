FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize database and ingest data
RUN python -m app.data.ingest_excel
RUN python -m app.rag.ingest_documents

# Expose port
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "app/frontend/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
