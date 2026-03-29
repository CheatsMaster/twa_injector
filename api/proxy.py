import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return Redis(url=url, token=token) if url and token else None

redis_client = get_redis()

class handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')
            password = body.get('password')
            tg_id = str(body.get('tg_id', 'unknown'))
            
            if not password or not tg_id:
                return self.send_json({"error": "Auth required"}, 401)

            db_key = f"user:{tg_id}:auth"

            # РЕГИСТРАЦИЯ (Привязка пароля к Secret Key для конкретного ID)
            if action == 'register':
                secret_key = body.get('secret_key')
                if not secret_key: return self.send_json({"error": "Secret Key required"}, 400)
                
                # Сохраняем связку в Redis: { "pass": "...", "s_key": "..." }
                redis_client.set(db_key, json.dumps({"pass": password, "s_key": secret_key}))
                return self.send_json({"status": "ok"})

            # ПРОВЕРКА ВХОДА И ПРАВ
            stored_data = redis_client.get(db_key)
            if not stored_data:
                return self.send_json({"error": "User not found"}, 401)
            
            auth_info = json.loads(stored_data)
            if auth_info['pass'] != password:
                return self.send_json({"error": "Wrong password"}, 401)

            if action == 'login':
                return self.send_json({"status": "ok"})

            # ПРОКСИРОВАНИЕ К SELLER API
            path = body.get('path')
            method = body.get('method', 'GET')
            payload = body.get('payload')
            
            req = urllib.request.Request(
                f"http://95.181.213.84:8081{path}",
                data=json.dumps(payload).encode('utf-8') if payload else None,
                headers={
                    'X-Seller-Key': auth_info['s_key'],
                    'Content-Type': 'application/json'
                },
                method=method
            )

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    return self.send_json(json.loads(response.read().decode('utf-8')))
            except urllib.error.HTTPError as e:
                return self.send_json({"error": "API Error"}, e.code)

        except Exception as e:
            self.send_json({"error": str(e)}, 500)
