FROM petoo/pdf2docx:0.5.13-py311-static

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/common

COPY services/common /app/common
COPY services/pdf2docx-worker /app/service

CMD ["python", "/app/service/worker.py"]
