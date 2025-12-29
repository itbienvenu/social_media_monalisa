# Specialized Social Media Platform Backend

A production-ready backend monorepo for a "Post Once, Publish Everywhere" platform.

## Architecture

Microservices architecture built with:
- **Python 3.11**
- **FastAPI**
- **PostgreSQL**: Configured on port `5433` (host) mapped to `5432` (container) to avoid conflicts.
- **Docker & Docker Compose**

### Services

- `api-gateway`: Authentication and routing.
- `post-orchestrator`: Manages post creation and orchestration.
- `platform-posting-services`: Workers for Facebook, TikTok, LinkedIn.
- `analytics-collector`: Background job for fetching metrics.
- `analytics-api`: Read-only API for analytics.

## Running Locally

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Build and run services:
   ```bash
   docker-compose up --build
   ```

3. Access endpoints:
   - API Gateway: http://localhost:8000
   - Analytics API: http://localhost:8001
