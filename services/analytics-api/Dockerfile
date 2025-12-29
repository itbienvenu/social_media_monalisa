FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY services/analytics-api/requirements.txt ./services/analytics-api/requirements.txt

RUN pip install --no-cache-dir -r services/analytics-api/requirements.txt databases[postgresql]

COPY libs /app/libs
COPY services/analytics-api /app/services/analytics_api
# Also copy collector models to share DB definition if needed, or better, make it shared. 
# For now, I'll copy the collector models, or better yet, define it in api as well or move to libs/common/models.
# Since user asked for "PostgreSQL schema for posts, post_targets, post_metrics_snapshot", 
# I should have put DB models in libs/common/db.py if I wanted to share.
# But for now, I'll duplicate the model definition or just query raw SQL for simplicity in API.
# Let's import from analytics-collector if I can, but they are separate services. 
# Best practice: Shared library. I'll stick to defining table in router.py or db.py in analytics-api.

# Actually, I can just copy the models.py from analytics-collector during build if I wanted, 
# but clean separation means defining it again or using shared lib. 
# I already made `services/analytics-collector/models.py`. 
# I'll create `services/analytics-api/db.py` with the same definition.

COPY services/analytics-collector/models.py /app/services/analytics_api/models.py

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.analytics_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
