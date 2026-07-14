#!/usr/bin/env python3
import os
import http.server
import socketserver
from pathlib import Path

PORT = 8080

class ATSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_POST(self):
        # Handle form submission
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # Log submission
        print(f"Received POST data: {post_data[:200]}...")
        
        # Return success
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = b'{"success": true, "application_id": "MOCK-12345"}'
        self.wfile.write(response)

if __name__ == '__main__':
    # Change to the mock-ats directory
    os.chdir(Path(__file__).parent)
    
    with socketserver.TCPServer(("0.0.0.0", PORT), ATSHandler) as httpd:
        print(f"Mock ATS Server running at http://0.0.0.0:{PORT}")
        print(f"Access the application form at http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.shutdown()
