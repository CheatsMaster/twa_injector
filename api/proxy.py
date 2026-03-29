import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

def get_redis():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
    return Redis(url=url, token=token)

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
                return self.send_json({"error": "ID и пароль обязательны"}, 401)

            if redis_client is None:
                return self.send_json({"error": "Redis не настроен в Vercel"}, 500)

            db_key = f"user:{tg_id}:auth"

            # РЕГИСТРАЦИЯ С ПРОВЕРКОЙ КЛЮЧА
            if action == 'register':
                secret_key = body.get('secret_key')
                if not secret_key: 
                    return self.send_json({"error": "Введите Secret Key"}, 400)
                
                # Проверяем ключ через запрос списка продуктов
                check_req = urllib.request.Request(
                    "http://95.181.213.84:8081/api/seller/products",
                    headers={'X-Seller-Key': secret_key},
                    method='GET'
                )
                try:
                    with urllib.request.urlopen(check_req, timeout=5) as resp:
                        res_data = json.loads(resp.read().decode('utf-8'))
                        if res_data.get("status") != "ok":
                            return self.send_json({"error": "Ключ продавца невалиден"}, 400)
                except Exception:
                    return self.send_json({"error": "Не удалось проверить ключ (ошибка API)"}, 400)

                # Если проверка прошла — сохраняем
                redis_client.set(db_key, json.dumps({"pass": password, "s_key": secret_key}))
                return self.send_json({"status": "ok"})

            # ПРОВЕРКА ВХОДА
            stored = redis_client.get(db_key)
            if not stored:
                return self.send_json({"error": "Аккаунт не найден. Зарегистрируйтесь."}, 401)
            
            auth_info = json.loads(stored)
            if auth_info['pass'] != password:
                return self.send_json({"error": "Неверный пароль"}, 401)

            if action == 'login':
                return self.send_json({"status": "ok"})

            # ВЫПОЛНЕНИЕ ЗАПРОСОВ К SELLER API
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

            with urllib.request.urlopen(req, timeout=10) as response:
                return self.send_json(json.loads(response.read().decode('utf-8')))

        except Exception as e:
            self.send_json({"error": str(e)}, 500)
