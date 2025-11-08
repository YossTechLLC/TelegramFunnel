# Use the official lightweight Python image.
FROM python:3.11-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set workdir
WORKDIR /app

# Install system dependencies for cloud services and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY tps10-26.py .
COPY config_manager.py .
COPY changenow_client.py .
COPY database_manager.py .

# Expose the port
EXPOSE 8080

# Set the entrypoint
CMD ["python", "tps10-26.py"]