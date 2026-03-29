import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis_client():
    url = os.environ.get("STORAGE_REST_API_URL") or os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("STORAGE_REST_API_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
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
            if not redis:
                return self.send_json({"error": "Redis not connected. Check Vercel Storage settings."}, 500)

            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')
            password = body.get('password')
            
            if not password:
                return self.send_json({"error": "No password provided"}, 401)

            # --- Регистрация ---
            if action == 'register':
                s_key = body.get('secret_key')
                if not s_key: return self.send_json({"error": "Secret Key required"}, 400)
                redis.set(f"auth:{password}", s_key)
                return self.send_json({"status": "ok", "message": "Registered"})

            # --- Получение ключа из базы ---
            stored_secret = redis.get(f"auth:{password}")
            if not stored_secret:
                return self.send_json({"error": "Wrong password"}, 401)

            # Если это байты (иногда Redis возвращает bytes), декодируем
            if isinstance(stored_secret, bytes):
                stored_secret = stored_secret.decode('utf-8')
            
            if action == 'login':
                return self.send_json({"status": "ok"})

            # --- Запрос к твоему API ---
            path = body.get('path', '/api/seller/keys')
            method = body.get('method', 'GET')
            payload = body.get('payload')

            target_url = f"http://95.181.213.84:8081{path}"
            
            # Важно: превращаем stored_secret в чистую строку
            token_str = str(stored_secret).strip()

            req = urllib.request.Request(
                target_url,
                data=json.dumps(payload).encode('utf-8') if payload else None,
                headers={
                    'X-Seller-Key': token_str,
                    'Content-Type': 'application/json'
                },
                method=method
            )

            try:
                with urllib.request.urlopen(req, timeout=8) as response:
                    raw_res = response.read().decode('utf-8')
                    return self.send_json(json.loads(raw_res))
            except urllib.error.HTTPError as e:
                # Если твой сервер вернул 4xx или 5xx, пробрасываем это
                return self.send_json({"error": f"Server API Error: {e.code}", "details": e.read().decode()}, e.code)
            except Exception as e:
                return self.send_json({"error": f"Connection failed: {str(e)}"}, 502)

        except Exception as e:
            return self.send_json({"error": f"Internal Proxy Error: {str(e)}"}, 500)
