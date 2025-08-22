# /app/utils.py

from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .models import User

def require_api_key(f):
    """
    Decorator untuk melindungi endpoint.
    Hanya mengizinkan akses jika header 'X-API-KEY' valid.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        
        if api_key and api_key == current_app.config['APP_API_KEY']:
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Akses tidak diizinkan atau kunci API salah"}), 401
    return decorated_function


# --- DECORATOR YANG SUDAH DIPERBAIKI DAN AMAN ---
def require_admin_role(f):
    """
    Decorator untuk memastikan HANYA admin yang bisa mengakses endpoint.
    Ini secara otomatis akan mewajibkan token login (JWT) yang valid.
    """
    @wraps(f)
    @jwt_required() # 1. Wajibkan token login yang valid di sini
    def decorated_function(*args, **kwargs):
        # 2. Ambil ID pengguna dari token, BUKAN dari body request
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        # 3. Periksa peran dari user yang sudah terotentikasi
        if user and user.role_id == 1: # Asumsi role_id 1 adalah admin
            # Jika user adalah admin, lanjutkan ke fungsi endpoint
            return f(*args, **kwargs)
        else:
            # Jika bukan admin, tolak akses
            return jsonify({"error": "Akses ditolak. Tindakan ini hanya untuk admin."}), 403 # 403 Forbidden
    return decorated_function