#!/usr/bin/env sh
echo "--- Starting Startup Script ---"
echo "Current working directory: $(pwd)"
echo "Listing files in current directory:"
ls -la

# Ensure data directory exists
mkdir -p data

# Check if database exists
if [ ! -f "data/restaurants.db" ]; then
    echo "Database file data/restaurants.db not found! Running ingestion..."
    python scripts/ingest_dataset.py
else
    echo "Database file data/restaurants.db found."
fi

echo "Launching uvicorn on port $PORT..."
exec uvicorn StitchUIDesign.server:app --host 0.0.0.0 --port "$PORT"
