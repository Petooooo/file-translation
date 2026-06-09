FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/common

COPY services/common /app/common
COPY services/job-service /app/service

EXPOSE 8080
CMD ["python", "/app/service/app.py"]
