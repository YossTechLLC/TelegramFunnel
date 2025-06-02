# ---- build stage (slim) ----------------------------------------------------
FROM python:3.11-slim

# minimal OS deps for python-telegram-bot (certifi already included)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY main.py .

# Cloud Run looks for PORT env-var
ENV PORT=8080

# use gunicorn to serve the Flask app
CMD ["gunicorn", "-b", ":8080", "main:app"]
