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

## Testing and Verifying Published Posts

### Facebook Post Verification
When a post is successfully published to Facebook, the `facebook-service` logs or publishes a success message containing a `platform_post_id`. The format of this ID is:
`{page_id}_{post_id}` (for example, `690471164140335_122189425328870730`).

To verify if the post (and any associated media or images) was successfully created on Facebook, you can construct a direct permalink using either of the following URL structures:

1. **Direct ID Link (Recommended)**:
   Append the full `platform_post_id` directly to the Facebook domain:
   ```text
   https://www.facebook.com/{platform_post_id}
   ```
   *Example:* [https://www.facebook.com/690471164140335_122189425328870730](https://www.facebook.com/690471164140335_122189425328870730)

2. **Standard Page Post Link**:
   Split the `platform_post_id` at the underscore (`_`) into `{page_id}` (before) and `{post_id}` (after):
   ```text
   https://www.facebook.com/{page_id}/posts/{post_id}
   ```
   *Example:* [https://www.facebook.com/690471164140335/posts/122189425328870730](https://www.facebook.com/690471164140335/posts/122189425328870730)

> [!NOTE]
> These links will only render the post if the Facebook Page and the post itself are published and public, or if you are logged into a Facebook account that has administrative or developer access to the page/application.

## Post Lifecycle Logging Engine

We have introduced an advanced lifecycle logging engine that tracks every transition stage of a post as it propagates through the services. This helps diagnose where and why a post might have failed (e.g., media download failures, platform API rejections, network timeouts).

### Querying Logs for a Post
To get a full log of all lifecycle transitions for a specific post, make a GET request to the `post-orchestrator`:

```http
GET http://localhost:8000/posts/{post_id}/logs
```

### Supported Stages & Statuses
The following events are recorded in the shared database `post_logs` table:
*   **`post_created`**: The post was stored in the orchestrator database.
*   **`event_published`**: The orchestrator dispatched the post event to the message broker (RabbitMQ).
*   **`event_received`**: The target platform worker received the posting event.
*   **`downloading_media`**: The worker is pulling the media files from MinIO / object storage.
*   **`media_downloaded`**: Media files were successfully downloaded locally by the worker.
*   **`media_download_failed`**: Media download failed (automatically triggers a URL-based upload fallback).
*   **`posting_to_platform`**: The worker is calling the external social media Graph API.
*   **`platform_success` / `post_success`**: The post was successfully created on the platform.
*   **`platform_failed` / `post_failed`**: The posting process failed (includes the error details/reason).

## Post Scheduling System

A timezone-aware scheduling system has been integrated into the post orchestrator service, enabling future publication, rescheduling, cancellation, and background execution.

### Database Additions
*   `scheduled_at`: The datetime (UTC) when the post is scheduled to run.
*   `timezone`: The original user's local timezone (e.g. `US/Eastern`).
*   `scheduler_status`: The status of scheduling (`scheduled`, `publishing`, `published`, `cancelled`).
*   `retry_count`: Tracks retries in case of transient failures (max 3).
*   `last_attempt_at`: Timestamp of the last execution attempt.

### API Endpoints
1.  **Schedule a Post**:
    *   `POST /posts?user_id={id}`: Provide `"scheduled_at": "YYYY-MM-DDTHH:MM:SSZ"` and `"timezone": "Europe/London"` in the body.
2.  **Cancel a Post**:
    *   `POST /posts/{post_id}/cancel`: Sets scheduler status to `cancelled` and status to `failed`.
3.  **Reschedule/Edit a Post**:
    *   `PUT /posts/{post_id}`: Reschedule a cancelled/failed/scheduled post to a new time and update its content/timezone.

### Background Worker
An ARQ worker runs a cron job (`check_scheduled_posts`) every minute to pick up due posts, publish them via RabbitMQ, handle retries with an exponential/fixed delay, and emit warning notifications for users in case of retries or failures.

