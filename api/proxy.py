from http.server import BaseHTTPRequestHandler
import urllib.request
import json
import os
from upstash_redis import Redis # Библиотека для работы с KV

# Подключаемся к базе через переменные Vercel
redis = Redis.from_env()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))
        
        action = body.get('action')
        password = body.get('password')

        # 1. Регистрация (первый вход)
        if action == 'register':
            s_key = body.get('secret_key')
            # Сохраняем ключ под паролем (в жизни лучше хешировать, но для начала так)
            redis.set(f"user_auth_{password}", s_key)
            return self.send_json({"status": "ok", "message": "Registered"})

        # 2. Обычный запрос (Прокси)
        s_key = redis.get(f"user_auth_{password}")
        if not s_key:
            return self.send_json({"status": "error", "message": "Wrong Password"}, 401)

        # Выполняем запрос к основному API
        res = self.make_api_request(body.get('path'), body.get('payload', {}), s_key, body.get('method', 'GET'))
        self.send_json(res)

    def make_api_request(self, path, payload, s_key, method):
        target = "http://95.181.213.84:8081" + path.replace('/api', '/api/seller')
        req = urllib.request.Request(
            target,
            data=json.dumps(payload).encode() if method == 'POST' else None,
            headers={'X-Seller-Key': s_key, 'Content-Type': 'application/json'},
            method=method
        )
        try:
            with urllib.request.urlopen(req) as r: return json.loads(r.read())
        except Exception as e: return {"status": "error", "message": str(e)}

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
