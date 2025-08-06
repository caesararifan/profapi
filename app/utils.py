# /my-api-project/app/utils.py

from functools import wraps
from flask import request, jsonify, current_app

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if api_key and api_key == current_app.config['APP_API_KEY']:
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Akses tidak diizinkan atau kunci API salah"}), 401
    return decorated_function