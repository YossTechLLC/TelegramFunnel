# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install PGP_COMMON shared library
COPY ../PGP_COMMON /tmp/PGP_COMMON
RUN pip install -e /tmp/PGP_COMMON

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run application
CMD ["python", "pgp_notifications_v1.py"]
