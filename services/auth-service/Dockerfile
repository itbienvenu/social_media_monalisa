FROM python:3.11-slim

WORKDIR /app

COPY services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/auth-service /app/services/auth_service
COPY libs /app/libs

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.auth_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
