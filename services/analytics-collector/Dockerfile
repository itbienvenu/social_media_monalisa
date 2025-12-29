FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/analytics-collector/requirements.txt ./services/analytics-collector/requirements.txt

RUN pip install --no-cache-dir -r services/analytics-collector/requirements.txt databases[postgresql]

COPY libs /app/libs
COPY services/analytics-collector /app/services/analytics_collector

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.analytics_collector.main"]
