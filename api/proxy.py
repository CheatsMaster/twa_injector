import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis():
    # Ищем переменные STORAGE (как на твоем скриншоте) или стандартные KV
    url = os.environ.get("STORAGE_REST_API_URL") or os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("STORAGE_REST_API_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
    return Redis(url=url, token=token)

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
                return self.send_json({"error": "Redis не подключен. Проверь вкладку Storage в Vercel"}, 500)

            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')
            password = body.get('password')
            
            if not password:
                return self.send_json({"error": "Введите пароль"}, 401)

            # Регистрация
            if action == 'register':
                s_key = body.get('secret_key')
                if not s_key: return self.send_json({"error": "Нужен Secret Key"}, 400)
                redis_client.set(f"auth:{password}", s_key)
                return self.send_json({"status": "ok"})

            # Авторизация
            stored_secret = redis_client.get(f"auth:{password}")
            if not stored_secret:
                return self.send_json({"error": "Неверный пароль"}, 401)
            
            if isinstance(stored_secret, bytes):
                stored_secret = stored_secret.decode('utf-8')
            
            if action == 'login':
                return self.send_json({"status": "ok"})

            # Прокси к твоему серверу
            path = body.get('path', '/api/seller/keys')
            method = body.get('method', 'GET')
            payload = body.get('payload')
            target_url = f"http://95.181.213.84:8081{path}"
            
            encoded_data = json.dumps(payload).encode('utf-8') if payload and method == 'POST' else None

            req = urllib.request.Request(
                target_url,
                data=encoded_data,
                headers={'X-Seller-Key': str(stored_secret).strip(), 'Content-Type': 'application/json'},
                method=method
            )

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    return self.send_json(json.loads(response.read().decode('utf-8')))
            except urllib.error.HTTPError as e:
                return self.send_json({"error": f"Ошибка сервера: {e.code}"}, e.code)
            except Exception as e:
                return self.send_json({"error": f"Ошибка соединения: {str(e)}"}, 502)

        except Exception as e:
            return self.send_json({"error": f"Ошибка прокси: {str(e)}"}, 500)
