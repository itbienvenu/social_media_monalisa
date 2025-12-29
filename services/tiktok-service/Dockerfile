FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/tiktok-service/requirements.txt ./services/tiktok-service/requirements.txt

RUN pip install --no-cache-dir -r services/tiktok-service/requirements.txt

COPY libs /app/libs
COPY services/tiktok-service /app/services/tiktok_service

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.tiktok_service.main"]
