FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/api-gateway/requirements.txt ./services/api-gateway/requirements.txt

# Install dependencies (merging shared libs reqs if we had any, simplifying here)
RUN pip install --no-cache-dir -r services/api-gateway/requirements.txt

COPY libs /app/libs
COPY services/api-gateway /app/services/api_gateway

# We need to set PYTHONPATH so we can import 'services.api_gateway' and 'libs'
ENV PYTHONPATH=/app

CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
