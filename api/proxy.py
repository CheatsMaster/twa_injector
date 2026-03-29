import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis_client():
    # Проверяем все возможные префиксы Vercel
    url = os.environ.get("STORAGE_REST_API_URL") or os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("STORAGE_REST_API_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        raise ValueError("Redis credentials missing in Environment Variables")
    return Redis(url=url, token=token)

redis = get_redis_client()

class handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_json({"status": "ok"})

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')
            password = body.get('password')
            
            if not password:
                return self.send_json({"error": "Password required"}, 401)

            # --- РЕГИСТРАЦИЯ ---
            if action == 'register':
                s_key = body.get('secret_key')
                if not s_key:
                    return self.send_json({"error": "Secret Key required"}, 400)
                redis.set(f"auth:{password}", s_key)
                return self.send_json({"status": "ok", "message": "Registered"})

            # --- ПРОВЕРКА ПАРОЛЯ ---
            stored_secret = redis.get(f"auth:{password}")
            if not stored_secret:
                return self.send_json({"error": "Invalid password"}, 401)

            if action == 'login':
                return self.send_json({"status": "ok"})

            # --- ПРОКСИРОВАНИЕ ---
            path = body.get('path', '/api/seller/keys')
            method = body.get('method', 'GET')
            payload = body.get('payload')

            target_url = f"http://95.181.213.84:8081{path}"
            
            req = urllib.request.Request(
                target_url,
                data=json.dumps(payload).encode('utf-8') if payload else None,
                headers={
                    'X-Seller-Key': str(stored_secret),
                    'Content-Type': 'application/json'
                },
                method=method
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return self.send_json(res_data)

        except Exception as e:
            # Отправляем текст ошибки, чтобы ты увидел её в браузере
            return self.send_json({"error": str(e)}, 500)

    def do_GET(self):
        self.send_json({"status": "error", "message": "Use POST for all actions"}, 405)
