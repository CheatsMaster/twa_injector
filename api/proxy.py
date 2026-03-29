from http.server import BaseHTTPRequestHandler
import urllib.request
import json

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.proxy_request('POST')

    def do_GET(self):
        self.proxy_request('GET')

    def proxy_request(self, method):
        target_host = "http://95.181.213.84:8081"
        secret_key = "0169484D028595B485C406FEE11F3C86F331B7823D6D10B6"
        
        # Перенаправляем /api/keys -> /api/seller/keys
        path = self.path.replace('/api', '/api/seller')
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(
            target_host + path,
            data=body,
            headers={
                'X-Seller-Key': secret_key,
                'Content-Type': 'application/json'
            },
            method=method
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = response.read()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(res_data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
