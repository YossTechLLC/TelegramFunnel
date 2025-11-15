# Dockerfile for GCSplit2-10-26 (USDT→ETH Estimator Service)
# Multi-stage build for optimal image size

FROM python:3.10-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies (including PostgreSQL client libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# ===== MIGRATION: Copy shared library =====
# Copy shared library BEFORE service files
# This allows the service files to import from _shared/
COPY _shared/ /app/_shared/

# ===== Service-specific files =====
# Copy application code
COPY tps2-10-26.py .
COPY config_manager.py .
COPY token_manager.py .
COPY cloudtasks_client.py .
# NOTE: changenow_client.py is now imported from _shared/
COPY database_manager.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

# Expose port 8080
EXPOSE 8080

# Run the application
CMD ["python", "tps2-10-26.py"]
