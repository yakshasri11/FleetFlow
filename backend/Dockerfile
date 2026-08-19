FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Runs migrations, then starts the API. On free hosts the DB may take a
# moment to accept connections, hence the small retry loop.
CMD sh -c "\
    for i in 1 2 3 4 5; do alembic upgrade head && break || sleep 5; done && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
