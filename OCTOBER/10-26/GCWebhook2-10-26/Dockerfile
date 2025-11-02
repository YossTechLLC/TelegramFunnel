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

# Copy the app code
COPY config_manager.py .
COPY token_manager.py .
COPY database_manager.py .
COPY tph2-10-26.py .

# Expose the port
EXPOSE 8080

# Set the entrypoint
CMD ["python", "tph2-10-26.py"]
