# Build from the repository root:
#   docker build -f services/triage_processor/Dockerfile -t triage-processor .
FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 CONFIG_DIR=/srv/config FRONTEND_DIR=/srv/frontend
WORKDIR /srv
COPY services/triage_processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/triage_processor/app ./app
COPY config ./config
COPY --from=ui /ui/dist ./frontend
RUN useradd -r app
USER app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
