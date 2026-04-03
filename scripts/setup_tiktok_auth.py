#!/usr/bin/env python3
"""Helper script to set up TikTok OAuth2 authentication.

TikTok requires OAuth2 to get an access token. This script helps you
through the flow:

1. Go to https://developers.tiktok.com/ and create an app
2. Add "Content Posting API" scope
3. Run this script to get your access token
"""

import http.server
import urllib.parse
import webbrowser
import requests
from config.settings import settings

REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

access_token = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global access_token
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            code = params["code"][0]
            print(f"\nAuthorization code received: {code[:20]}...")

            # Exchange code for access token
            token_data = {
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            }
            resp = requests.post(TOKEN_URL, data=token_data, timeout=30)
            token_resp = resp.json()

            if "access_token" in token_resp.get("data", {}):
                access_token = token_resp["data"]["access_token"]
                refresh_token = token_resp["data"].get("refresh_token", "")
                print(f"\nAccess Token: {access_token}")
                print(f"Refresh Token: {refresh_token}")
                print("\nAdd this to your .env file:")
                print(f"TIKTOK_ACCESS_TOKEN={access_token}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Success! You can close this window.")
            else:
                print(f"Token exchange failed: {token_resp}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Failed to get token. Check console.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No authorization code received.")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def main():
    if not settings.TIKTOK_CLIENT_KEY or not settings.TIKTOK_CLIENT_SECRET:
        print("ERROR: Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env first")
        print("Get these from https://developers.tiktok.com/")
        return

    auth_params = urllib.parse.urlencode({
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "user.info.basic,video.publish",
    })

    auth_link = f"{AUTH_URL}?{auth_params}"
    print("Opening TikTok authorization page...")
    print(f"If browser doesn't open, go to:\n{auth_link}\n")
    webbrowser.open(auth_link)

    print("Waiting for callback on localhost:8080...")
    server = http.server.HTTPServer(("localhost", 8080), CallbackHandler)
    server.handle_request()  # Handle one request then stop


if __name__ == "__main__":
    main()
