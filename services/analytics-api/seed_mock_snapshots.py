import os
import urllib.parse
import datetime
import random
from sqlalchemy import create_engine, MetaData, Table, select, insert

DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "social_platform")

password_encoded = urllib.parse.quote_plus(DB_PASSWORD)
user_encoded = urllib.parse.quote_plus(DB_USER)

DATABASE_URL = f"postgresql://{user_encoded}:{password_encoded}@{DB_HOST}:{DB_PORT}/{DB_NAME}"



def seed_analytics():
    engine = create_engine(DATABASE_URL)
    metadata = MetaData()
    metadata.reflect(bind=engine)

    posts_table = metadata.tables['posts']
    snapshots_table = metadata.tables['analytics_snapshots']

    with engine.connect() as conn:
        # Get all posts
        posts = conn.execute(select(posts_table)).fetchall()
        print(f"Found {len(posts)} posts in DB.")

        if not posts:
            print("No posts found to associate snapshots with.")
            return

        # Delete existing snapshots to re-seed cleanly
        conn.execute(snapshots_table.delete())
        
        # Insert historical snapshots for each post over the last 30 days
        inserted = 0
        for post in posts:
            post_id = post.id
            platforms = [post.platform] if post.platform else ['facebook', 'instagram']
            is_reel = post.is_reel
            
            # Base views and engagement for the post
            base_views = random.randint(500, 10000) if is_reel else random.randint(100, 2000)
            base_likes = int(base_views * random.uniform(0.05, 0.15))
            base_comments = int(base_likes * random.uniform(0.05, 0.2))
            base_shares = int(base_likes * random.uniform(0.01, 0.1))

            # Seed snapshots across the last 30 days
            created_time = post.created_at or (datetime.datetime.utcnow() - datetime.timedelta(days=35))
            
            # We want daily snapshots
            for day in range(30):
                snap_time = created_time + datetime.timedelta(days=day)
                if snap_time > datetime.datetime.utcnow():
                    break
                
                # Metrics grow over time
                growth_factor = (day + 1) / 30.0
                likes = int(base_likes * growth_factor)
                comments = int(base_comments * growth_factor)
                shares = int(base_shares * growth_factor)
                views = int(base_views * growth_factor)

                for plat in platforms:
                    import uuid
                    conn.execute(
                        insert(snapshots_table).values(
                            id=uuid.uuid4(),
                            post_id=post_id,
                            platform=plat,
                            views=views,
                            likes=likes,
                            comments=comments,
                            shares=shares,
                            timestamp=snap_time
                        )
                    )
                    inserted += 1

        print(f"Successfully seeded {inserted} analytics snapshots.")

if __name__ == "__main__":
    seed_analytics()
