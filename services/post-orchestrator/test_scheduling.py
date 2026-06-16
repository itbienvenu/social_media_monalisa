import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
import json
from datetime import datetime, timedelta
import zoneinfo

from httpx import AsyncClient, ASGITransport
from libs.common.serializers import PostStatus, Platform

class TestPostScheduling(unittest.IsolatedAsyncioTestCase):
    
    @classmethod
    def setUpClass(cls):
        # 1. First import modules
        from services.post_orchestrator.main import app
        from services.post_orchestrator.db import database, Post, PostTarget, Notification, metadata
        import services.post_orchestrator.tasks as tasks
        
        cls.app = app
        cls.database = database
        cls.Post = Post
        cls.PostTarget = PostTarget
        cls.Notification = Notification
        cls.metadata = metadata
        cls.tasks = tasks

        # 2. Patch the imported publish_post_event references in main and tasks
        cls.main_publish_patcher = patch("services.post_orchestrator.main.publish_post_event", new_callable=AsyncMock)
        cls.mock_main_publish = cls.main_publish_patcher.start()
        
        cls.tasks_publish_patcher = patch("services.post_orchestrator.tasks.publish_post_event", new_callable=AsyncMock)
        cls.mock_tasks_publish = cls.tasks_publish_patcher.start()

        # 3. Manually run migrations to ensure database is up-to-date
        import sqlalchemy
        engine = sqlalchemy.create_engine(str(database.url))
        cls.metadata.create_all(engine)
        with engine.begin() as conn:
            inspector = sqlalchemy.inspect(engine)
            if "posts" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("posts")]
                if "facebook_page_id" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN facebook_page_id VARCHAR"))
                if "retry_count" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN retry_count INTEGER DEFAULT 0"))
                if "last_attempt_at" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN last_attempt_at TIMESTAMP"))

    @classmethod
    def tearDownClass(cls):
        cls.main_publish_patcher.stop()
        cls.tasks_publish_patcher.stop()

    async def asyncSetUp(self):
        # Setup patchers to isolate from external dependencies
        self.mq_connect_patcher = patch("services.post_orchestrator.main.mq.connect", new_callable=AsyncMock)
        self.mock_mq_connect = self.mq_connect_patcher.start()
        
        self.mq_subscribe_patcher = patch("services.post_orchestrator.main.mq.subscribe", new_callable=AsyncMock)
        self.mock_mq_subscribe = self.mq_subscribe_patcher.start()
        
        self.mq_disconnect_patcher = patch("services.post_orchestrator.main.mq.disconnect", new_callable=AsyncMock)
        self.mock_mq_disconnect = self.mq_disconnect_patcher.start()
        
        self.mock_arq_pool = MagicMock()
        self.mock_arq_pool.close = AsyncMock()
        self.create_pool_patcher = patch("services.post_orchestrator.main.create_pool", return_value=self.mock_arq_pool)
        self.mock_create_pool = self.create_pool_patcher.start()

        # Connect DB on test loop and keep it connected during the test run
        try:
            if self.database.is_connected:
                await self.database.disconnect()
        except Exception:
            pass
        await self.database.connect()
        await self.database.execute(self.PostTarget.delete())
        await self.database.execute(self.Notification.delete())
        await self.database.execute(self.Post.delete())

        # Reset mocks
        self.mock_main_publish.reset_mock()
        self.mock_tasks_publish.reset_mock()

    async def asyncTearDown(self):
        # Clean up database and disconnect
        try:
            await self.database.execute(self.PostTarget.delete())
            await self.database.execute(self.Notification.delete())
            await self.database.execute(self.Post.delete())
        except Exception:
            pass
            
        try:
            if self.database.is_connected:
                await self.database.disconnect()
        except Exception:
            pass

        self.mq_connect_patcher.stop()
        self.mq_subscribe_patcher.stop()
        self.mq_disconnect_patcher.stop()
        self.create_pool_patcher.stop()

    async def test_create_scheduled_post_success(self):
        # Create a scheduled post 1 hour in the future
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        payload = {
            "content": "Test scheduled post content",
            "platforms": ["facebook"],
            "media_key": None,
            "media_keys": [],
            "is_reel": False,
            "scheduled_at": future_time,
            "timezone": "America/New_York"
        }
        
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.post("/posts", json=payload, params={"user_id": "test-user-123"})
            
        self.assertEqual(response.status_code, 200, msg=f"Response status not 200: {response.status_code}, content: {response.text}")
        data = response.json()
        
        self.assertEqual(data["scheduler_status"], "scheduled")
        self.assertEqual(data["timezone"], "America/New_York")
        self.assertIsNotNone(data["scheduled_at"])
        
        # Verify no immediate RabbitMQ event was published
        self.mock_main_publish.assert_not_called()
        self.mock_tasks_publish.assert_not_called()
        
        # Verify database record
        post_id = data["id"]
        post_record = await self.database.fetch_one(self.Post.select().where(self.Post.c.id == uuid.UUID(post_id)))
        
        self.assertIsNotNone(post_record)
        self.assertEqual(post_record["scheduler_status"], "scheduled")
        self.assertEqual(post_record["timezone"], "America/New_York")

    async def test_create_scheduled_post_past_time_fails(self):
        # Try to schedule a post 1 hour in the past
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        payload = {
            "content": "Test past scheduled post",
            "platforms": ["facebook"],
            "scheduled_at": past_time,
            "timezone": "UTC"
        }
        
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.post("/posts", json=payload, params={"user_id": "test-user-123"})
            
        self.assertEqual(response.status_code, 400, msg=f"Response status not 400: {response.status_code}, content: {response.text}")
        self.assertIn("Scheduled time must be in the future", response.json()["detail"])

    async def test_create_scheduled_post_invalid_timezone_fails(self):
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        payload = {
            "content": "Test invalid tz scheduled post",
            "platforms": ["facebook"],
            "scheduled_at": future_time,
            "timezone": "Invalid/Timezone"
        }
        
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.post("/posts", json=payload, params={"user_id": "test-user-123"})
            
        self.assertEqual(response.status_code, 400, msg=f"Response status not 400: {response.status_code}, content: {response.text}")
        self.assertIn("Invalid timezone", response.json()["detail"])

    async def test_cancel_scheduled_post(self):
        # First, insert a scheduled post directly
        post_id = uuid.uuid4()
        await self.database.execute(
            self.Post.insert().values(
                id=post_id,
                user_id="test-user-123",
                content="To be cancelled",
                status=PostStatus.PENDING.value,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                scheduled_at=datetime.utcnow() + timedelta(hours=1),
                timezone="UTC",
                scheduler_status="scheduled"
            )
        )
        await self.database.execute(
            self.PostTarget.insert().values(
                id=uuid.uuid4(),
                post_id=post_id,
                platform="facebook",
                status="pending"
            )
        )
        
        # Cancel the post
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.post(f"/posts/{post_id}/cancel")
            
        self.assertEqual(response.status_code, 200, msg=f"Response status not 200: {response.status_code}, content: {response.text}")
        data = response.json()
        self.assertEqual(data["scheduler_status"], "cancelled")
        self.assertEqual(data["status"], PostStatus.FAILED.value)
        
        # Check targets are cancelled
        target = await self.database.fetch_one(self.PostTarget.select().where(self.PostTarget.c.post_id == post_id))
        self.assertEqual(target["status"], "cancelled")

    async def test_update_reschedule_post(self):
        # Insert a cancelled scheduled post
        post_id = uuid.uuid4()
        await self.database.execute(
            self.Post.insert().values(
                id=post_id,
                user_id="test-user-123",
                content="To be rescheduled",
                status=PostStatus.FAILED.value,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                scheduled_at=datetime.utcnow() - timedelta(hours=1),
                timezone="UTC",
                scheduler_status="cancelled"
            )
        )
        await self.database.execute(
            self.PostTarget.insert().values(
                id=uuid.uuid4(),
                post_id=post_id,
                platform="facebook",
                status="cancelled"
            )
        )
        
        # Reschedule it to 2 hours in the future
        future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z"
        payload = {
            "content": "Updated content",
            "scheduled_at": future_time,
            "timezone": "Europe/London"
        }
        
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.put(f"/posts/{post_id}", json=payload)
            
        self.assertEqual(response.status_code, 200, msg=f"Response status not 200: {response.status_code}, content: {response.text}")
        data = response.json()
        self.assertEqual(data["scheduler_status"], "scheduled")
        self.assertEqual(data["timezone"], "Europe/London")
        self.assertEqual(data["status"], PostStatus.PENDING.value)
        
        # Target status should be reset to pending
        target = await self.database.fetch_one(self.PostTarget.select().where(self.PostTarget.c.post_id == post_id))
        self.assertEqual(target["status"], "pending")

    async def test_cron_worker_picks_up_and_publishes(self):
        # Insert a scheduled post that is due
        post_id = uuid.uuid4()
        await self.database.execute(
            self.Post.insert().values(
                id=post_id,
                user_id="test-user-123",
                content="Scheduled now",
                status=PostStatus.PENDING.value,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                scheduled_at=datetime.utcnow() - timedelta(minutes=5),  # Due 5 mins ago
                timezone="UTC",
                scheduler_status="scheduled"
            )
        )
        await self.database.execute(
            self.PostTarget.insert().values(
                id=uuid.uuid4(),
                post_id=post_id,
                platform="facebook",
                status="pending"
            )
        )
        
        # Run the cron function
        await self.tasks.check_scheduled_posts(None)
        
        # Verify DB states
        post_record = await self.database.fetch_one(self.Post.select().where(self.Post.c.id == post_id))
        
        # Verify event was published and status is publishing
        self.mock_tasks_publish.assert_called_once()
        self.assertEqual(post_record["scheduler_status"], "publishing")
        
        # Simulate platform callback for success
        from services.post_orchestrator.main import handle_post_success
        
        # 1. Update post_target status first (simulate facebook-service reporting success)
        await self.database.execute(
            self.PostTarget.update().where(
                (self.PostTarget.c.post_id == post_id) & 
                (self.PostTarget.c.platform == "facebook")
            ).values(status="published")
        )
        
        # 2. Call handler
        await handle_post_success({"post_id": str(post_id)}, "facebook")
        
        # 3. Verify final DB states
        post_record = await self.database.fetch_one(self.Post.select().where(self.Post.c.id == post_id))
        self.assertEqual(post_record["scheduler_status"], "published")
        self.assertEqual(post_record["status"], PostStatus.PUBLISHED.value)

    @patch("services.post_orchestrator.tasks.publish_post_event", side_effect=Exception("RabbitMQ connection error"))
    async def test_cron_worker_retry_mechanism(self, mock_publish_event_fail):
        # Insert a scheduled post that is due
        post_id = uuid.uuid4()
        await self.database.execute(
            self.Post.insert().values(
                id=post_id,
                user_id="test-user-123",
                content="Retry test",
                status=PostStatus.PENDING.value,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                scheduled_at=datetime.utcnow() - timedelta(minutes=1),
                timezone="UTC",
                scheduler_status="scheduled",
                retry_count=0
            )
        )
        await self.database.execute(
            self.PostTarget.insert().values(
                id=uuid.uuid4(),
                post_id=post_id,
                platform="facebook",
                status="pending"
            )
        )
        
        # Run cron function
        await self.tasks.check_scheduled_posts(None)
        
        # Verify DB states updated to retry
        post_record = await self.database.fetch_one(self.Post.select().where(self.Post.c.id == post_id))
        
        # Check target status reset to pending
        target = await self.database.fetch_one(self.PostTarget.select().where(self.PostTarget.c.post_id == post_id))
        
        # Verify notification created
        notifications = await self.database.fetch_all(self.Notification.select().where(self.Notification.c.user_id == "test-user-123"))
        
        self.assertEqual(post_record["scheduler_status"], "scheduled")  # Kept scheduled
        self.assertEqual(post_record["retry_count"], 1)
        self.assertTrue(post_record["scheduled_at"] > datetime.utcnow() + timedelta(minutes=4))  # scheduled for +5 mins
        self.assertEqual(target["status"], "pending")
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], "Scheduled post retry")
