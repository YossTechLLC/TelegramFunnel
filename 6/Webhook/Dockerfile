# Use the official lightweight Python image.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY invite_webhook.py ./

# Set environment variable for Flask
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=invite_webhook.py

# Expose port (Cloud Run expects 8080)
EXPOSE 8080

# Run via Gunicorn for production
CMD exec gunicorn -b :8080 invite_webhook:app
