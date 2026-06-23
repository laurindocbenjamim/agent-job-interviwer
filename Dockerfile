FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgles2 \
    libegl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config files
COPY src/ ./src/
COPY .env* ./

# Expose port 8000
EXPOSE 8000

# Run the app using uvicorn
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
