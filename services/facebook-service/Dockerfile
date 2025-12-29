FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/facebook-service/requirements.txt ./services/facebook-service/requirements.txt

RUN pip install --no-cache-dir -r services/facebook-service/requirements.txt

COPY libs /app/libs
COPY services/facebook-service /app/services/facebook_service

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.facebook_service.main"]
