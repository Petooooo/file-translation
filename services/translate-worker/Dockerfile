FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/common

COPY services/common /app/common
COPY services/translate-worker /app/service

CMD ["python", "/app/service/worker.py"]
