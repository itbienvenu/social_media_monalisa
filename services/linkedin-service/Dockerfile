FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/linkedin-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs /app/libs
COPY services/linkedin-service /app/services/linkedin_service

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.linkedin_service.main"]
