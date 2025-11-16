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

# Install PGP_COMMON shared library
COPY PGP_COMMON/ /app/PGP_COMMON/
RUN pip install -e /app/PGP_COMMON

# Copy the app code
COPY config_manager.py .
COPY token_manager.py .
COPY database_manager.py .
COPY pgp_invite_v1.py .

# Expose the port
EXPOSE 8080

# Set the entrypoint
CMD ["python", "pgp_invite_v1.py"]
