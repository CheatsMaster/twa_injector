import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

# Универсальный поиск ключей в переменных Vercel
# Он проверит и STORAGE_REST_API_URL, и KV_REST_API_URL, и другие варианты
def get_redis_client():
    url = (
        os.environ.get("STORAGE_REST_API_URL") or 
        os.environ.get("KV_REST_API_URL") or 
        os.environ.get("UPSTASH_REDIS_REST_URL")
    )
    token = (
        os.environ.get("STORAGE_REST_API_TOKEN") or 
        os.environ.get("KV_REST_API_TOKEN") or 
        os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    )
    
    if not url or not token:
        # Если это упадет, значит Vercel не пробросил ключи
        raise ValueError("Database keys not found. Go to Vercel Project Settings -> Environment Variables and check them.")
    
    return Redis(url=url, token=token)

redis = get_redis_client()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body_raw = self.rfile.read(content_length)
        
        try:
            data = json.loads(body_raw)
        except:
            return self.send_json({"status": "error", "message": "Invalid JSON"}, 400)

        action = data.get('action')
        password = data.get('password')
        
        if not password:
            return self.send_json({"status": "error", "message": "Password required"}, 401)

        # 1. Логика регистрации (первый вход)
        if action == 'register':
            secret_key = data.get('secret_key')
            if not secret_key:
                return self.send_json({"status": "error", "message": "Secret Key required for registration"}, 400)
            
            # Сохраняем связку в Redis на долгосрок
            redis.set(f"auth:{password}", secret_key)
            return self.send_json({"status": "ok", "message": "Registered successfully"})

        # 2. Логика проверки и проксирования
        stored_secret = redis.get(f"auth:{password}")
        
        if not stored_secret:
            return self.send_json({"status": "error", "message": "Invalid password or not registered"}, 401)

        # Если это был просто вход (login) без запроса к API
        if action == 'login':
            return self.send_json({"status": "ok", "message": "Authenticated"})

        # 3. Проксирование запроса к твоему основному API [cite: 1, 4]
        path = data.get('path', '/api/seller/keys')
        method = data.get('method', 'GET')
        payload = data.get('payload')

        target_url = f"http://95.181.213.84:8081{path}" # [cite: 1]
        
        req_headers = {
            'X-Seller-Key': stored_secret, # [cite: 2]
            'Content-Type': 'application/json'
        }

        req_data = json.dumps(payload).encode('utf-8') if payload else None
        
        request = urllib.request.Request(target_url, data=req_data, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                res_body = response.read().decode('utf-8')
                return self.send_json(json.loads(res_body))
        except Exception as e:
            return self.send_json({"status": "error", "message": str(e)}, 500)

    def send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # Для работы из браузера
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    # Добавляем обработку OPTIONS для CORS (браузеры часто шлют его перед POST)
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
