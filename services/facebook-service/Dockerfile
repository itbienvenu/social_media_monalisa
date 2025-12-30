FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/facebook-service/requirements.txt ./services/facebook-service/requirements.txt

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir -r services/facebook-service/requirements.txt

COPY libs /app/libs
COPY services/facebook-service /app/services/facebook_service

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.facebook_service.main"]
