FROM python:3.11-slim

WORKDIR /app

COPY services/instagram-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs /app/libs
COPY services/instagram-service /app/services/instagram_service

CMD ["python", "-m", "services.instagram_service.main"]
