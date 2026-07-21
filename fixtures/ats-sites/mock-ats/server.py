#!/usr/bin/env python3
import json
import os
import http.server
import socketserver
from pathlib import Path

PORT = 8080

# Server-process-lifetime account store, simulating a real ATS's backend
# database. Deliberately NOT localStorage/client-side - browser automation
# creates a fresh, isolated context per run (by design, matching real
# incognito-style isolation), so client-side storage can't simulate account
# persistence across separate login attempts the way a real server-side
# account would. This is what actually makes credential-vault reuse
# (get_or_create_credential returning a previously-created account, then
# successfully logging back in from a brand new browser context) verifiable.
_ACCOUNTS = {}


class ATSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(content_length) if content_length else b'{}'
        return json.loads(raw or b'{}')

    def do_POST(self):
        if self.path == '/api/signup':
            data = self._read_json()
            email = data.get('email', '')
            password = data.get('password', '')
            if not email or not password:
                self._send_json(400, {'success': False, 'error': 'email and password are required'})
                return
            if email in _ACCOUNTS:
                self._send_json(409, {'success': False, 'error': 'An account with this email already exists'})
                return
            _ACCOUNTS[email] = password
            self._send_json(200, {'success': True})
            return

        if self.path == '/api/login':
            data = self._read_json()
            email = data.get('email', '')
            password = data.get('password', '')
            if _ACCOUNTS.get(email) == password:
                self._send_json(200, {'success': True})
            else:
                self._send_json(401, {'success': False, 'error': 'Incorrect email or password'})
            return

        # Fallback for any other POST (not used by the current client-side
        # submit flow, which redirects rather than posting, kept for parity
        # with older direct-POST test scripts).
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length else b''
        print(f"Received POST to {self.path}: {post_data[:200]}...")
        self._send_json(200, {'success': True, 'application_id': 'MOCK-12345'})


if __name__ == '__main__':
    os.chdir(Path(__file__).parent)

    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), ATSHandler) as httpd:
        print(f"Mock ATS Server running at http://0.0.0.0:{PORT}")
        print(f"Access the application form at http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.shutdown()
