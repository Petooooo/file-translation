FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/common

COPY services/docx-extract-worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/common /app/common
COPY services/docx-extract-worker /app/service

CMD ["python", "/app/service/worker.py"]
