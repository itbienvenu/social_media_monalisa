import asyncio
import httpx
import os
from dotenv import load_dotenv

# Load .env explicitly
load_dotenv()

APP_ID = os.getenv("FACEBOOK_APP_ID")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
API_VERSION = os.getenv("FACEBOOK_API_VERSION", "v18.0")

async def verify_credentials():
    print(f"--- Verifying Facebook App Credentials ---")
    print(f"App ID: {APP_ID}")
    # Don't print the full secret
    print(f"App Secret: {APP_SECRET[:4]}...{APP_SECRET[-4:] if APP_SECRET else ''}")
    print(f"API Version: {API_VERSION}")

    if not APP_ID or not APP_SECRET:
        print("❌ Error: credentials missing in .env")
        return

    url = f"https://graph.facebook.com/{API_VERSION}/oauth/access_token"
    params = {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "grant_type": "client_credentials"
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"\nRequesting App Access Token from {url}...")
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Success! Credentials are valid.")
                print(f"App Access Token received: {data.get('access_token')[:10]}...")
            else:
                print(f"❌ Failed! Status Code: {response.status_code}")
                print(f"Response: {response.text}")

        except Exception as e:
            print(f"❌ Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(verify_credentials())
