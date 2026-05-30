# Use official lightweight Python image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install system compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Run dataset ingestion during the build phase so database is packaged into the image
RUN python scripts/ingest_dataset.py

# Expose port
EXPOSE 8000

# Start FastAPI backend instantly to pass Railway health checks
CMD ["sh", "-c", "uvicorn StitchUIDesign.server:app --host 0.0.0.0 --port $PORT"]
