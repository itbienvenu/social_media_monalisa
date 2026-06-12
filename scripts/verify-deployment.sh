#!/bin/bash
# Exit on error, and treat pipeline failures as errors
set -eo pipefail

# Load .env so POSTGRES_USER / POSTGRES_DB are available
set -a
[ -f .env ] && source .env
set +a

echo "=== Verifying Docker Container Status ==="
docker compose ps

# Inspect for unhealthy containers.
# Two fixes applied here:
#  1. State check: catches ALL non-running states (restarting, exited, dead,
#     created, paused, etc.) — the old filter missed crash-looping containers
#     whose state is 'restarting'.
#  2. jq filter: wraps input with [.[]] so it handles both output formats of
#     'docker compose ps --format json': a JSON array (Compose v2.20+) and a
#     stream of newline-delimited JSON objects (older versions).
UNHEALTHY_SERVICES=$(docker compose ps --format json \
  | jq -r '[.[]] | .[] | select(.State != "running") | .Service' || true)
RUNNING_COUNT=$(docker compose ps --format json \
  | jq -r '[.[]] | .[] | select(.State == "running") | .Service' | wc -l || echo 0)

if [ "$RUNNING_COUNT" -eq 0 ]; then
  echo "❌ No containers are running at all. Build likely failed or containers crashed on startup."
  docker compose logs --tail=200
  exit 1
fi
if [ -n "$UNHEALTHY_SERVICES" ]; then
  echo "❌ One or more Docker services are not running: $UNHEALTHY_SERVICES"
  docker compose logs --tail=200
  exit 1
fi
echo "✓ All $RUNNING_COUNT containers are running."

echo "=== Checking Auth Service /health endpoint ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused --retry-all-errors http://localhost:8002/health || (
  echo "❌ Auth service health check failed at http://localhost:8002/health"
  docker compose logs auth-service --tail=200
  exit 1
)
echo "✓ Auth service is healthy."

echo "=== Checking API Gateway /docs endpoint ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused --retry-all-errors http://localhost:8000/docs || (
  echo "❌ API Gateway health check failed"
  docker compose logs api-gateway --tail=200
  exit 1
)
echo "✓ API Gateway is healthy."

echo "=== Checking Analytics API /docs endpoint ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused --retry-all-errors http://localhost:8001/docs || (
  echo "❌ Analytics API health check failed"
  docker compose logs analytics-api --tail=200
  exit 1
)
echo "✓ Analytics API is healthy."

echo "=== Checking PostgreSQL Connectivity ==="
# Run pg_isready inside the container's own shell so it automatically uses
# the POSTGRES_USER and POSTGRES_DB env vars that docker-compose injected —
# no hardcoded values, no dependency on the host environment.
docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' || (
  echo "❌ PostgreSQL connectivity check failed."
  docker compose logs db --tail=200
  exit 1
)
echo "✓ PostgreSQL is accepting connections."

echo "=== Checking Redis Connectivity ==="
docker compose exec -T redis redis-cli ping | grep -q "PONG" || (
  echo "❌ Redis connectivity check failed."
  docker compose logs redis --tail=200
  exit 1
)
echo "✓ Redis is accepting connections."

echo "=== Checking RabbitMQ Connectivity ==="
docker compose exec -T rabbitmq rabbitmq-diagnostics -q ping || (
  echo "❌ RabbitMQ connectivity check failed."
  docker compose logs rabbitmq --tail=200
  exit 1
)
echo "✓ RabbitMQ connectivity check passed."

echo "=== Checking MinIO Connectivity ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused --retry-all-errors http://localhost:9000/minio/health/live || (
  echo "❌ MinIO connectivity check failed"
  docker compose logs minio --tail=200
  exit 1
)
echo "✓ MinIO connectivity check passed."

echo "=== Deployment Verified Successfully ==="
