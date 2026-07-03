import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from httpx import AsyncClient, ASGITransport
from services.post_orchestrator.main import app
from services.post_orchestrator.db import database, Post, PostTarget, Notification, metadata
from libs.common.db_models import SocialAccount, SocialTarget
import services.post_orchestrator.tasks as tasks
import sqlalchemy

class TestPostMultiAccount(unittest.IsolatedAsyncioTestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.database = database
        cls.Post = Post
        cls.PostTarget = PostTarget
        cls.Notification = Notification
        cls.metadata = metadata
        cls.tasks = tasks
        cls.SocialAccount = SocialAccount
        cls.SocialTarget = SocialTarget

        cls.main_publish_patcher = patch("services.post_orchestrator.main.publish_post_event", new_callable=AsyncMock)
        cls.mock_main_publish = cls.main_publish_patcher.start()
        
        cls.tasks_publish_patcher = patch("services.post_orchestrator.tasks.publish_post_event", new_callable=AsyncMock)
        cls.mock_tasks_publish = cls.tasks_publish_patcher.start()

        engine = sqlalchemy.create_engine(str(database.url))
        cls.metadata.create_all(engine)

    @classmethod
    def tearDownClass(cls):
        cls.main_publish_patcher.stop()
        cls.tasks_publish_patcher.stop()

    async def asyncSetUp(self):
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

        try:
            if self.database.is_connected:
                await self.database.disconnect()
        except Exception:
            pass
        await self.database.connect()
        await self.database.execute(self.PostTarget.delete())
        await self.database.execute(self.Notification.delete())
        await self.database.execute(self.Post.delete())
        await self.database.execute(self.SocialTarget.delete())
        await self.database.execute(self.SocialAccount.delete())

        self.mock_main_publish.reset_mock()
        self.mock_tasks_publish.reset_mock()

    async def asyncTearDown(self):
        try:
            await self.database.execute(self.PostTarget.delete())
            await self.database.execute(self.Notification.delete())
            await self.database.execute(self.Post.delete())
            await self.database.execute(self.SocialTarget.delete())
            await self.database.execute(self.SocialAccount.delete())
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

    async def test_create_post_with_targets_success(self):
        # 1. Insert a mock social account and targets
        account_id = uuid.uuid4()
        await self.database.execute(
            self.SocialAccount.insert().values(
                id=account_id,
                user_id="test-user-123",
                platform="facebook",
                platform_user_id="fb-user-1",
                account_name="Test FB Account"
            )
        )
        await self.database.execute(
            self.SocialTarget.insert().values(
                id=uuid.uuid4(),
                target_id="fb-page-123",
                account_id=account_id,
                platform="facebook",
                target_name="My Cool Page",
                target_type="page"
            )
        )
        
        payload = {
            "content": "Testing multi-account targeted post!",
            "target_ids": ["fb-page-123"],
            "media_key": None,
            "media_keys": [],
            "is_reel": False
        }
        
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.post("/posts", json=payload, params={"user_id": "test-user-123"})
            
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["platforms"], ["facebook"])
        
        # Verify PostTarget was saved with the target_id
        post_target = await self.database.fetch_one(
            self.PostTarget.select().where(self.PostTarget.c.post_id == uuid.UUID(data["id"]))
        )
        self.assertIsNotNone(post_target)
        self.assertEqual(post_target["platform"], "facebook")
        self.assertEqual(post_target["target_id"], "fb-page-123")
        
        # Verify event was published with the target_id
        self.mock_main_publish.assert_called_once()
        args, kwargs = self.mock_main_publish.call_args
        self.assertEqual(kwargs["target_id"], "fb-page-123")

    async def test_create_post_with_invalid_target_fails(self):
        # Using a target ID that does not exist/belong to user
        payload = {
            "content": "Should fail",
            "target_ids": ["invalid-page-id"],
            "media_key": None,
            "media_keys": [],
            "is_reel": False
        }
        
        async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
            response = await client.post("/posts", json=payload, params={"user_id": "test-user-123"})
            
        self.assertEqual(response.status_code, 400)
        self.assertIn("No valid social targets found matching the target_ids", response.text)
