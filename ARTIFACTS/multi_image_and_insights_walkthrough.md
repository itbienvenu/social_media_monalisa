# Multi-Image Publishing & Real-time Insights Walkthrough

We have successfully implemented and verified the system-wide capabilities for:
1. **Publishing Multiple Images** to Facebook in a single post (via pre-signed multipart uploads to MinIO and Facebook's detached media attachment API).
2. **Exposing & Visualizing Real-time Insights** directly on the application dashboard.

---

## 1. Architecture Flow for Multi-Image Publishing

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend
    participant MinIO
    participant Post Orchestrator
    participant RabbitMQ
    participant Facebook Service
    participant Facebook API

    User->>Frontend: Selects multiple images & drafts text
    loop Each File
        Frontend->>Post Orchestrator: POST /media/upload-url (Get Presigned URL)
        Post Orchestrator-->>Frontend: Presigned PUT URL & Public GET URL
        Frontend->>MinIO: PUT image binary
    end
    Frontend->>Post Orchestrator: POST /posts {content, media_keys: [URLs]}
    Post Orchestrator->>Post Orchestrator: Save post record with JSON-serialized media_keys
    Post Orchestrator->>RabbitMQ: Publish posts.facebook event (with media_urls list)
    RabbitMQ-->>Facebook Service: Consume event
    loop Each media URL
        Facebook Service->>MinIO: Download image binary
        Facebook Service->>Facebook API: POST /{page_id}/photos {published: false}
        Facebook API-->>Facebook Service: Return photo ID
    end
    Facebook Service->>Facebook API: POST /{page_id}/feed {message: content, attached_media: [photo_ids]}
    Facebook API-->>Facebook Service: Return feed post ID
    Facebook Service->>RabbitMQ: Publish posts.facebook.success (with platform_post_id)
```

---

## 2. Real-Time Insights & Analytics Architecture

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend
    participant Post Orchestrator
    participant Facebook Service
    participant Facebook API

    User->>Frontend: Clicks "Insights" on dashboard post
    Frontend->>Post Orchestrator: GET /posts/{post_id}/metrics
    Post Orchestrator->>Post Orchestrator: Look up external_id in post_targets
    Post Orchestrator->>Facebook Service: GET /posts/{external_id}/metrics
    Facebook Service->>Facebook API: GET /{external_id} (likes, comments, shares)
    Facebook Service->>Facebook API: GET /{external_id}/insights (reach/impressions)
    Facebook API-->>Facebook Service: Return API counts & values
    Facebook Service-->>Post Orchestrator: Return formatted metrics
    Post Orchestrator-->>Frontend: Return aggregated metrics
    Frontend-->>User: Display gorgeous stats modal
```

---

## 3. Implemented Components

### Backend
1. **Schema & Models**:
   - `media_keys` added to Pydantic serializers in `libs/common/serializers.py` and postgres schema in `services/post-orchestrator/db.py`.
   - Automatic migrations handles schema updates during orchestrator startup.
2. **RabbitMQ Event System**:
   - Updates `publish_post_event` in `services/post-orchestrator/events.py` to forward all internal MinIO public URLs under a list `media_urls`.
3. **Facebook Service**:
   - Added `post_multiple_photos` method inside `FacebookClient` which downloads binaries internally from MinIO, uploads them as unpublished media items, and binds them to a single feed post.
   - Added `get_post_metrics` logic supporting real-time likes, comments, shares, and unique impressions.

### Frontend
1. **Create Post View** (`frontend/src/app/post/page.tsx`):
   - Accepts multiple images via local selection.
   - Shows detailed upload progress for each image sequentially.
   - Passes all storage URLs under `media_keys` to the orchestrator.
2. **Dashboard Feed & Insights** (`frontend/src/app/dashboard/page.tsx`):
   - Displays image thumbnails on the activity feed.
   - Added an **Insights** action button.
   - Includes a beautifully crafted glassmorphism modal with KPI cards (Estimated Reach, Reactions, Comments, Shares) and per-platform breakdown sections.
