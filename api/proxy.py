import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis():
    url = os.environ.get("STORAGE_REST_API_URL") or os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("STORAGE_REST_API_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return Redis(url=url, token=token) if url and token else None

redis_client = get_redis()

class handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_json({"status": "ok"})

    def do_POST(self):
        try:
            if not redis_client:
                return self.send_json({"error": "Redis не настроен"}, 500)

            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')
            password = body.get('password')
            
            if not password: return self.send_json({"error": "No password"}, 401)

            # Регистрация / Логин
            if action == 'register':
                s_key = body.get('secret_key')
                if not s_key: return self.send_json({"error": "Secret Key required"}, 400)
                redis_client.set(f"auth:{password}", s_key)
                return self.send_json({"status": "ok"})

            stored_secret = redis_client.get(f"auth:{password}")
            if not stored_secret: return self.send_json({"error": "Invalid password"}, 401)
            
            if isinstance(stored_secret, bytes):
                stored_secret = stored_secret.decode('utf-8')
            
            if action == 'login': return self.send_json({"status": "ok"})

            # Прокси к Seller API 
            path = body.get('path')
            method = body.get('method', 'GET')
            payload = body.get('payload')
            
            target_url = f"http://95.181.213.84:8081{path}"
            
            encoded_data = json.dumps(payload).encode('utf-8') if payload else None

            # Важно: Передаем X-Seller-Key в заголовке 
            req = urllib.request.Request(
                target_url,
                data=encoded_data,
                headers={
                    'X-Seller-Key': str(stored_secret).strip(),
                    'Content-Type': 'application/json'
                },
                method=method
            )

            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    return self.send_json(json.loads(response.read().decode('utf-8')))
            except urllib.error.HTTPError as e:
                return self.send_json({"error": f"API Error {e.code}"}, e.code)
            except Exception as e:
                return self.send_json({"error": str(e)}, 502)

        except Exception as e:
            return self.send_json({"error": str(e)}, 500)
