import httpx

def test_google_auth():
    print("Testing Google Auth Endpoint Flow (inside container)...")
    # Gateway URL is accessible inside docker network as api-gateway:8000
    gateway_url = "http://api-gateway:8000"
    
    # 1. Get Google Auth URL
    print("Step 1: Fetching Google auth URL...")
    url_resp = httpx.get(f"{gateway_url}/auth/google/url")
    assert url_resp.status_code == 200, f"Expected 200, got {url_resp.status_code}"
    url_data = url_resp.json()
    print("Auth URL Data:", url_data)
    assert "url" in url_data, "Expected 'url' in response"
    
    # 2. Trigger Google Callback with mock_google_code
    print("Step 2: Triggering callback with mock code...")
    # Follow redirects=False to capture the redirect location
    callback_resp = httpx.get(
        f"{gateway_url}/auth/google/callback",
        params={"code": "mock_google_code"},
        follow_redirects=False
    )
    print("Callback Status Code:", callback_resp.status_code)
    assert callback_resp.status_code in (302, 307), f"Expected 302 redirect, got {callback_resp.status_code}"
    
    redirect_url = callback_resp.headers.get("location")
    print("Redirect Location:", redirect_url)
    assert redirect_url is not None, "Expected Location header in RedirectResponse"
    assert "/login?access_token=" in redirect_url, "Redirect URL should contain access_token"
    
    # Extract tokens from the redirect URL
    import urllib.parse as urlparse
    parsed = urlparse.urlparse(redirect_url)
    queries = urlparse.parse_qs(parsed.query)
    
    access_token = queries.get("access_token")[0]
    refresh_token = queries.get("refresh_token")[0]
    print("Extracted Access Token:", access_token[:15] + "...")
    print("Extracted Refresh Token:", refresh_token[:15] + "...")
    
    # 3. Verify the token using /me endpoint proxy
    print("Step 3: Verifying retrieved token...")
    # auth-service has /me endpoint: GET /me?token={token}
    # Can access auth-service directly on localhost:8000 inside the container
    auth_service_url = "http://localhost:8000"
    me_resp = httpx.get(f"{auth_service_url}/me", params={"token": access_token})
    print("Me response status:", me_resp.status_code)
    assert me_resp.status_code == 200, f"Expected 200, got {me_resp.status_code}"
    me_data = me_resp.json()
    print("User Profile info from token:", me_data)
    assert me_data.get("email") == "mock_google_user@example.com", f"Expected mock_google_user@example.com, got {me_data.get('email')}"
    print("Google Auth Flow validation completed successfully!")

if __name__ == "__main__":
    test_google_auth()
