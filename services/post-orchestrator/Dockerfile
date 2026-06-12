FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
COPY services/post-orchestrator/requirements.txt ./services/post-orchestrator/requirements.txt

# Install dependencies (incorporating database driver)
RUN pip install --no-cache-dir -r services/post-orchestrator/requirements.txt databases[postgresql]

COPY libs /app/libs
COPY services/post-orchestrator /app/services/post_orchestrator

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.post_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
