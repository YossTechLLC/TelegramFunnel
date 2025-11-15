# PGP_WEBAPI_v1 Dockerfile
# Flask REST API for Channel Registration
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install PGP_COMMON shared library
COPY ../PGP_COMMON /tmp/PGP_COMMON
RUN pip install -e /tmp/PGP_COMMON

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run Flask app
CMD ["python", "pgp_webapi_v1.py"]
