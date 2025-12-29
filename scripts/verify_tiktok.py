import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

async def verify_tiktok_credentials():
    print(f"--- Verifying TikTok App Credentials ---")
    print(f"Client Key: {CLIENT_KEY}")
    print(f"Client Secret: {CLIENT_SECRET[:4]}...{CLIENT_SECRET[-4:] if CLIENT_SECRET else ''}")

    if not CLIENT_KEY or not CLIENT_SECRET:
        print(" Error: credentials missing in .env")
        return

    
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": "invalid_code_test", 
        "grant_type": "authorization_code",
        "redirect_uri": "http://localhost:8000/auth/tiktok/callback"
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"\nSending test request to {url}...")
            response = await client.post(url, data=data, headers=headers)
            
            print(f"Status Code: {response.status_code}")
            resp_json = response.json()
            print(f"Response: {resp_json}")
            
            # Analyze response
            # If Client Key is invalid -> usually explicit error about client
            # If Code is invalid -> error about code (which means client was likely checked first)
            
            err = resp_json.get("error", "")
            desc = resp_json.get("error_description", "")
            
            if "client" in desc.lower() or "client" in err.lower():
                 print(" Possible Credential Error: The API rejected your Client Key/Secret.")
            elif "code" in desc.lower() or "code" in err.lower() or "grant type" in desc.lower():
                 print(" Credentials appear valid! (API accepted the Client Key, but rejected our fake 'invalid_code_test' as expected).")
            else:
                 print(" Unknown response. Checks logs.")

        except Exception as e:
            print(f" Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(verify_tiktok_credentials())
