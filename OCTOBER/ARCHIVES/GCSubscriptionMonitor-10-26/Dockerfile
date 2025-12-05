# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY service.py .
COPY config_manager.py .
COPY database_manager.py .
COPY telegram_client.py .
COPY expiration_handler.py .

# Expose port
EXPOSE 8080

# Set environment variable for Python unbuffered output
ENV PYTHONUNBUFFERED=1

# Run application
CMD ["python", "service.py"]
