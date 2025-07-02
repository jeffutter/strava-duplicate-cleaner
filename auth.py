import json
import keyring
import requests
import webbrowser
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional
import threading
import time


class AuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/?'):
            query_params = parse_qs(urlparse(self.path).query)
            if 'code' in query_params:
                self.server.auth_code = query_params['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'''
                    <html><body>
                        <h1>Authorization Successful!</h1>
                        <p>You can close this window and return to the application.</p>
                    </body></html>
                ''')
            elif 'error' in query_params:
                self.server.auth_error = query_params['error'][0]
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body><h1>Authorization Failed</h1></body></html>')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class StravaAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8000"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.service_name = "strava-cleaner"

    def authenticate(self, scope: str = "read,activity:read_all") -> Optional[Dict]:
        auth_url = (
            f"https://www.strava.com/oauth/authorize"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&redirect_uri={self.redirect_uri}"
            f"&approval_prompt=force"
            f"&scope={scope}"
        )

        print(f"Opening browser for Strava authorization...")
        print(f"If browser doesn't open automatically, visit: {auth_url}")

        server = HTTPServer(('localhost', 8000), AuthCallbackHandler)
        server.auth_code = None
        server.auth_error = None

        webbrowser.open(auth_url)

        print("Waiting for authorization...")
        timeout = 300
        start_time = time.time()

        while server.auth_code is None and server.auth_error is None:
            server.handle_request()
            if time.time() - start_time > timeout:
                print("Authorization timeout. Please try again.")
                return None

        if server.auth_error:
            print(f"Authorization failed: {server.auth_error}")
            return None

        if server.auth_code:
            return self._exchange_code_for_token(server.auth_code)

        return None

    def _exchange_code_for_token(self, code: str) -> Optional[Dict]:
        token_url = "https://www.strava.com/oauth/token"

        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code'
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            tokens = response.json()

            self.save_tokens(tokens)
            print("Authentication successful!")
            return tokens

        except requests.exceptions.RequestException as e:
            print(f"Token exchange failed: {e}")
            return None

    def refresh_token(self, refresh_token: str) -> Optional[Dict]:
        token_url = "https://www.strava.com/oauth/token"

        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            tokens = response.json()

            self.save_tokens(tokens)
            return tokens

        except requests.exceptions.RequestException as e:
            print(f"Token refresh failed: {e}")
            return None

    def load_tokens(self) -> Optional[Dict]:
        try:
            token_json = keyring.get_password(self.service_name, "tokens")
            if token_json:
                return json.loads(token_json)
        except Exception as e:
            print(f"Failed to load tokens: {e}")
        return None

    def save_tokens(self, tokens: Dict):
        try:
            keyring.set_password(self.service_name, "tokens", json.dumps(tokens))
        except Exception as e:
            print(f"Failed to save tokens: {e}")

    def get_valid_access_token(self) -> Optional[str]:
        tokens = self.load_tokens()
        if not tokens:
            return None

        current_time = int(time.time())
        if tokens.get('expires_at', 0) <= current_time:
            refresh_token = tokens.get('refresh_token')
            if refresh_token:
                new_tokens = self.refresh_token(refresh_token)
                if new_tokens:
                    return new_tokens.get('access_token')
            return None

        return tokens.get('access_token')
