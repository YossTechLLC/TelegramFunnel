# Dockerfile for GCSplit3-10-26 (ETH→ClientCurrency Swapper Service)
# Multi-stage build for optimal image size

FROM python:3.10-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
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

# Copy application code
COPY tps3-10-26.py .
COPY config_manager.py .
COPY token_manager.py .
COPY cloudtasks_client.py .
COPY changenow_client.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

# Expose port 8080
EXPOSE 8080

# Run the application
CMD ["python", "tps3-10-26.py"]
