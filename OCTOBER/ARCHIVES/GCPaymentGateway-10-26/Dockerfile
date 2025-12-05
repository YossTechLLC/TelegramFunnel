# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY service.py .
COPY config_manager.py .
COPY database_manager.py .
COPY payment_handler.py .
COPY validators.py .

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Set environment variable for Python
ENV PYTHONUNBUFFERED=1

# Run the application using gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 service:app
