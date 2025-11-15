# Use the official lightweight Python image
FROM python:3.11-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy shared_utils from local directory (copied during build)
COPY shared_utils ./shared_utils

# Copy the app code
COPY cloudtasks_client.py .
COPY app.py .
COPY payment-processing.html .

# Expose the port
EXPOSE 8080

# Set the entrypoint
CMD ["python", "app.py"]
