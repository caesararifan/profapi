import os
import uuid
import random
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from functools import wraps
from xendit import Xendit, XenditError
from flask_bcrypt import Bcrypt

# Muat environment variables dari file .env
load_dotenv()
app = Flask(__name__)
bcrypt = Bcrypt(app)

# --- Konfigurasi Keamanan ---
APP_API_KEY = os.getenv('APP_API_KEY')
if not APP_API_KEY:
    raise ValueError("APP_API_KEY tidak ditemukan di environment. Harap set untuk keamanan.")

XENDIT_API_KEY = os.getenv('XENDIT_SECRET_KEY')
if not XENDIT_API_KEY:
    raise ValueError("XENDIT_SECRET_KEY tidak ditemukan di environment.")

# --- Simulasi Database Pengguna ---
# Di aplikasi produksi, ganti ini dengan koneksi ke database asli
users_db = {}

# --- Decorator untuk Otentikasi API Key ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if api_key and api_key == APP_API_KEY:
            return f(*args, **kwargs)
        else:
            app.logger.warning("Akses ditolak: API Key tidak valid atau tidak ada.")
            return jsonify({"error": "Akses tidak diizinkan"}), 401
    return decorated_function

# --- Endpoint Registrasi Pengguna ---
@app.route("/register", methods=["POST"])
@require_api_key
def handle_register_user():
    """
    Handle request untuk mendaftarkan pengguna baru.
    Membutuhkan: name, email, password.
    Mengembalikan PIN 6 digit untuk login.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body tidak valid (bukan JSON)"}), 400

    required_fields = ['name', 'email', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Field berikut wajib diisi: {', '.join(required_fields)}"}), 400

    name = data.get('name')
    email = data.get('email').lower()
    password = data.get('password')

    if email in users_db:
        return jsonify({"error": "Email sudah terdaftar"}), 409

    if len(password) < 8:
        return jsonify({"error": "Password minimal harus 8 karakter"}), 400

    # Buat user baru
    user_id = str(uuid.uuid4())
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    pin = str(random.randint(100000, 999999)) # PIN 6 digit acak

    users_db[email] = {
        "id": user_id,
        "name": name,
        "password_hash": hashed_password,
        "pin": pin # Simpan PIN untuk login
    }

    app.logger.info(f"✅ Pengguna baru terdaftar: {email} dengan user_id: {user_id}")

    return jsonify({
        "message": "Registrasi berhasil! Gunakan PIN ini untuk login.",
        "user_id": user_id,
        "pin": pin # Kembalikan PIN ke pengguna
    }), 201


# --- Endpoint Login Pengguna ---
@app.route("/login", methods=["POST"])
@require_api_key
def handle_login_user():
    """
    Handle request untuk login pengguna.
    Membutuhkan: email, password, dan pin.
    """
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password', 'pin']):
        return jsonify({"error": "Field email, password, dan pin wajib diisi"}), 400

    email = data.get('email', '').lower()
    password = data.get('password')
    pin = data.get('pin')
    
    user = users_db.get(email)

    # Verifikasi password DAN pin
    if not user or not bcrypt.check_password_hash(user.get('password_hash'), password) or user.get('pin') != pin:
        return jsonify({"error": "Email, password, atau PIN salah"}), 401

    app.logger.info(f"✅ Pengguna berhasil login: {email}")

    return jsonify({
        "message": "Login berhasil!",
        "user_id": user['id'],
        "name": user['name']
    })


# --- Fungsi dan Endpoint Xendit ---
def create_xendit_invoice(amount, description, payer_email):
    """
    Fungsi untuk membuat invoice di Xendit.
    """
    try:
        xendit_instance = Xendit(api_key=XENDIT_API_KEY)
        external_id = f"invoice-flask-{uuid.uuid4()}"
        app.logger.info(f"Membuat invoice untuk external_id: {external_id} dengan amount: {amount}")

        created_invoice = xendit_instance.Invoice.create(
            external_id=external_id,
            payer_email=payer_email,
            description=description,
            amount=amount
        )
        
        app.logger.info(f"✅ Invoice berhasil dibuat untuk external_id: {external_id}")
        return created_invoice, None

    except XenditError as e:
        app.logger.error(f"❌ Error dari Xendit: {e}")
        return None, f"Gagal berkomunikasi dengan layanan pembayaran: {e.error_code}"
    except Exception as e:
        app.logger.error(f"❌ Terjadi kesalahan tak terduga saat membuat invoice: {e}")
        return None, "Terjadi kesalahan internal pada server."

@app.route("/create-invoice", methods=["POST"])
@require_api_key
def handle_create_invoice():
    """
    Handle request untuk membuat invoice baru.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body tidak valid (bukan JSON)"}), 400

    required_fields = ['amount', 'description', 'payer_email']
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Field berikut wajib diisi: {', '.join(required_fields)}"}), 400

    amount = data.get('amount')
    description = data.get('description')
    payer_email = data.get('payer_email')

    if not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "'amount' harus berupa angka (integer) positif"}), 400
    
    invoice_object, error = create_xendit_invoice(amount, description, payer_email)

    if error:
        return jsonify({"error": "Gagal membuat invoice", "details": error}), 500
    
    return jsonify({
        "message": "Invoice berhasil dibuat!",
        "invoice_id": invoice_object.id,
        "external_id": invoice_object.external_id,
        "invoice_url": invoice_object.invoice_url
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)