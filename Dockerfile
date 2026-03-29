FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=app.main \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=8000

# Install system deps for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y vim && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "8000"]
