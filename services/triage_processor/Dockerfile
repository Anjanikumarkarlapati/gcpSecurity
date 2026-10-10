# Build from the repository root:
#   docker build -f services/triage_processor/Dockerfile -t triage-processor .
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 CONFIG_DIR=/srv/config
WORKDIR /srv
COPY services/triage_processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/triage_processor/app ./app
COPY config ./config
RUN useradd -r app
USER app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
