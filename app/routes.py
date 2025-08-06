# /my-api-project/app/routes.py

from flask import Blueprint, request, jsonify, current_app
from .models import User, Invoice
from . import db, bcrypt
from .utils import require_api_key
import random
import uuid
import base64
import requests

# Membuat 'Blueprint' untuk mengelompokkan rute-rute ini
main = Blueprint('main', __name__)

@main.route("/")
def index():
    return jsonify({"status": "ok", "message": "API Anda berjalan dengan baik!"})

@main.route("/register", methods=["POST"])
@require_api_key
def handle_register_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email dan password diperlukan"}), 400
    email = data.get('email').lower()
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email sudah terdaftar"}), 409
    
    hashed_password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    pin = str(random.randint(100000, 999999))
    
    new_user = User(
        name=data.get('name'), email=email, password_hash=hashed_password, pin=pin
    )
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "Registrasi berhasil!", "user_id": new_user.id, "pin": new_user.pin}), 201

@main.route("/login", methods=["POST"])
@require_api_key
def handle_login_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password') or not data.get('pin'):
        return jsonify({"error": "Email, password, dan PIN diperlukan"}), 400
    
    user = User.query.filter_by(email=data.get('email').lower()).first()
    
    if not user or not bcrypt.check_password_hash(user.password_hash, data.get('password')) or user.pin != data.get('pin'):
        return jsonify({"error": "Kredensial salah"}), 401
        
    return jsonify({"message": "Login berhasil!", "user_id": user.id, "name": user.name})

# --- Fungsi dan Endpoint Xendit ---
def create_xendit_invoice(amount, description, payer_email):
    xendit_key = current_app.config['XENDIT_API_KEY']
    url = "https://api.xendit.co/v2/invoices"
    external_id = f"invoice-flask-{uuid.uuid4()}"
    api_key_encoded = base64.b64encode(f"{xendit_key}:".encode()).decode()
    headers = {"Content-Type": "application/json", "Authorization": f"Basic {api_key_encoded}"}
    payload = {"external_id": external_id, "amount": amount, "payer_email": payer_email, "description": description}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.HTTPError as err:
        return None, err.response.json().get('message', 'Error tidak diketahui')
    except Exception as e:
        return None, str(e)

@main.route("/create-invoice", methods=["POST"])
@require_api_key
def handle_create_invoice():
    data = request.get_json()
    amount = data.get('amount')
    user_id = data.get('user_id') # <-- Minta user_id saat membuat invoice

    if not all([amount, user_id]):
        return jsonify({"error": "Jumlah (amount) dan user_id diperlukan"}), 400
    
    # Cek apakah user ada di database
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User tidak ditemukan"}), 404
        
    invoice_object, error = create_xendit_invoice(
        amount, 
        data.get('description', f'Pembayaran oleh {user.name}'), 
        user.email # Gunakan email user yang terdaftar
    )
    
    if error:
        return jsonify({"error": "Gagal membuat invoice", "details": error}), 500
    
    # ---- BAGIAN BARU: SIMPAN KE DATABASE ----
    new_invoice = Invoice(
        id=invoice_object.get('id'), # Gunakan ID dari Xendit sebagai ID kita
        external_id=invoice_object.get('external_id'),
        user_id=user.id,
        amount=invoice_object.get('amount'),
        status=invoice_object.get('status'),
        invoice_url=invoice_object.get('invoice_url')
    )
    db.session.add(new_invoice)
    db.session.commit()
    # ----------------------------------------
        
    return jsonify({
        "message": "Invoice berhasil dibuat dan dicatat!",
        "invoice_url": invoice_object.get('invoice_url')
    })