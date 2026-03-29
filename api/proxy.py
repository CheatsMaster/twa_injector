import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis():
    # Проверяем ВСЕ возможные имена переменных Vercel
    url = os.environ.get("STORAGE_REST_API_URL") or os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("STORAGE_REST_API_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
    return Redis(url=url, token=token)

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
            redis = get_redis()
            if not redis:
                return self.send_json({"error": "База данных Redis не подключена в Vercel Settings"}, 500)

            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')
            password = body.get('password')
            
            if not password:
                return self.send_json({"error": "Введите пароль"}, 401)

            # --- РЕГИСТРАЦИЯ ---
            if action == 'register':
                s_key = body.get('secret_key')
                if not s_key:
                    return self.send_json({"error": "Нужен Secret Key для первого входа"}, 400)
                redis.set(f"auth:{password}", s_key)
                return self.send_json({"status": "ok", "message": "Успешно сохранено!"})

            # --- ПРОВЕРКА ---
            stored_secret = redis.get(f"auth:{password}")
            # Важно: Upstash может вернуть строку или байты
            if hasattr(stored_secret, 'decode'):
                stored_secret = stored_secret.decode('utf-8')

            if not stored_secret:
                return self.send_json({"error": "Неверный пароль или аккаунт не создан"}, 401)

            if action == 'login':
                return self.send_json({"status": "ok"})

            # --- ПРОКСИ К API ---
            path = body.get('path', '/api/seller/keys')
            method = body.get('method', 'GET')
            target_url = f"http://95.181.213.84:8081{path}"
            
            req = urllib.request.Request(
                target_url,
                data=json.dumps(body.get('payload')).encode('utf-8') if body.get('payload') else None,
                headers={'X-Seller-Key': str(stored_secret), 'Content-Type': 'application/json'},
                method=method
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                return self.send_json(json.loads(response.read().decode('utf-8')))

        except Exception as e:
            # Если что-то сломается, мы увидим это в браузере!
            return self.send_json({"error": f"Ошибка в proxy.py: {str(e)}"}, 500)
