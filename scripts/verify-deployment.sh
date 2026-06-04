#!/bin/bash
# Exit on error
set -e

echo "=== Verifying Docker Container Status ==="
docker compose ps

# Inspect for crashed or exited containers
CRASHED_SERVICES=$(docker compose ps --format json | jq -r 'select(.State == "exited" or .State == "dead") | .Service' || true)
if [ ! -z "$CRASHED_SERVICES" ]; then
  echo "❌ One or more Docker services crashed or exited: $CRASHED_SERVICES"
  docker compose logs --tail=200
  exit 1
fi
echo "✓ All containers are running."

echo "=== Checking Auth Service /health endpoint ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused http://localhost:8002/health || (
  echo "❌ Auth service health check failed at http://localhost:8002/health"
  docker compose logs auth-service --tail=200
  exit 1
)
echo "✓ Auth service is healthy."

echo "=== Checking API Gateway /docs endpoint ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused http://localhost:8000/docs || (
  echo "❌ API Gateway health check failed"
  docker compose logs api-gateway --tail=200
  exit 1
)
echo "✓ API Gateway is healthy."

echo "=== Checking Analytics API /docs endpoint ==="
curl --fail --retry 10 --retry-delay 5 --retry-connrefused http://localhost:8001/docs || (
  echo "❌ Analytics API health check failed"
  docker compose logs analytics-api --tail=200
  exit 1
)
echo "✓ Analytics API is healthy."

echo "=== Checking PostgreSQL Connectivity ==="
docker compose exec -T db pg_isready -U user -d social_platform || (
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
curl --fail --retry 10 --retry-delay 5 --retry-connrefused http://localhost:9000/minio/health/live || (
  echo "❌ MinIO connectivity check failed"
  docker compose logs minio --tail=200
  exit 1
)
echo "✓ MinIO connectivity check passed."

echo "=== Deployment Verified Successfully ==="
