FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===== MIGRATION: Copy shared library =====
# Copy shared library BEFORE service files
COPY _shared/ /app/_shared/

# ===== Service-specific files =====
COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 microbatch10-26:app
