from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_mail import Message
from flask_jwt_extended import create_access_token
from ..models import User
import secrets
import uuid
from .. import db, bcrypt, mail
from ..utils import require_api_key


auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register/admin", methods=["POST"])
@require_api_key
def handle_admin_register():
    """Mendaftarkan pengguna baru sebagai ADMIN dengan kode rahasia."""
    data = request.get_json()
    if not data or not all(k in data for k in ['name', 'email','nomor_hp','password', 'admin_code']):
        return jsonify({"error": "Nama, email, nomor hp, password, dan kode admin diperlukan"}), 400
    
    if data.get('admin_code') != current_app.config['ADMIN_REGISTRATION_CODE']:
        return jsonify({"error": "Kode admin tidak valid"}), 403

    email = data.get('email').lower()
    nomor_hp = data.get('nomor_hp')

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email sudah terdaftar"}), 409
    if User.query.filter_by(nomor_hp=nomor_hp).first():
        return jsonify({"error": "Nomor HP sudah terdaftar"}), 409

    hashed_password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    
    new_user = User(
        id=str(uuid.uuid4()),
        name=data.get('name'), 
        email=email,
        nomor_hp=nomor_hp,
        password_hash=hashed_password, 
        role_id=1,
    )
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        "message": "Registrasi admin berhasil!", 
        "user_id": new_user.id
    }), 201

@auth_bp.route("/register/user", methods=["POST"])
@require_api_key
def handle_user_register():
    """Mendaftarkan pengguna baru sebagai USER BIASA."""
    data = request.get_json()
    if not data or not all(k in data for k in ['name', 'email', 'password', 'nomor_hp']):
        return jsonify({"error": "Nama, email, password, dan nomor hp diperlukan"}), 400
        
    email = data.get('email').lower()
    nomor_hp = data.get('nomor_hp')

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email sudah terdaftar"}), 409
    if User.query.filter_by(nomor_hp=nomor_hp).first():
        return jsonify({"error": "Nomor HP sudah terdaftar"}), 409

    hashed_password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    
    new_user = User(
        id=str(uuid.uuid4()),
        name=data.get('name'), 
        email=email,
        nomor_hp=nomor_hp,
        password_hash=hashed_password, 
        role_id=2,       
    )
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "Registrasi berhasil!", "user_id": new_user.id}), 201


@auth_bp.route("/login", methods=["POST"])
@require_api_key
def handle_user_login():
    """Melakukan login untuk pengguna biasa."""
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({"error": "Email, password diperlukan"}), 400
    
    user = User.query.filter_by(email=data.get('email').lower()).first()
    
    if not user or not bcrypt.check_password_hash(user.password_hash, data.get('password')):
        return jsonify({"error": "Kredensial salah"}), 401
    
    if user.role_id != 2:
        return jsonify({"error": "Akses ditolak. Gunakan halaman login admin."}), 403
    
    access_token = create_access_token(
        identity=user.id, 
        additional_claims={'role_id': user.role_id}
    )
        
    return jsonify({
        "message": "Login berhasil!", 
        "user_id": user.id, 
        "name": user.name,
        "role_id": user.role_id,
        "token": access_token
    })


@auth_bp.route("/admin/login", methods=["POST"])
@require_api_key
def handle_admin_login():
    """Melakukan login khusus untuk admin."""
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({"error": "Email, password diperlukan"}), 400
    
    admin = User.query.filter_by(email=data.get('email').lower()).first()
    
    if not admin or not bcrypt.check_password_hash(admin.password_hash, data.get('password')):
        return jsonify({"error": "Kredensial salah"}), 401
        
    if admin.role_id != 1:
        return jsonify({"error": "Akses ditolak. Anda bukan admin."}), 403

    access_token = create_access_token(
        identity=admin.id, 
        additional_claims={'role_id': admin.role_id}
    )
    
    return jsonify({
        "message": "Login Admin berhasil!", 
        "user_id": admin.id, 
        "name": admin.name,
        "role_id": admin.role_id,
        "token": access_token
    })

@auth_bp.route("/request-password-reset", methods=["POST"])
def request_password_reset():
    data = request.get_json()
    email = None
    
    if data:
        email = data.get('email')
    else:
        email = request.form.get('email')
    
    if not email:
        return jsonify({"error": "Email harus diisi"}), 400

    user = User.query.filter_by(email=email.lower()).first()
    
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        
        reset_link = f"http://{request.host}/halaman-reset-password/{token}"
        
        try:
            msg = Message(
                subject="Link Reset Password Anda",
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[user.email]
            )
            msg.body = f"Halo {user.name},\n\nKlik link ini untuk reset password:\n{reset_link}\n\nLink berlaku 1 jam."
            mail.send(msg)
            current_app.logger.info(f"Email reset password dikirim ke {user.email}")
        except Exception as e:
            current_app.logger.error(f"GAGAL KIRIM EMAIL: {str(e)}")
            return jsonify({"error": f"Error mengirim email: {str(e)}"}), 500
        
        return jsonify({"message": "Link reset sudah dikirim ke email Anda. Silakan periksa inbox atau spam."})
    else:
        # Untuk keamanan, kita tetap berikan respons sukses agar tidak bisa menebak email mana yang terdaftar
        return jsonify({"message": "Jika email Anda terdaftar, link reset akan dikirim."})

@auth_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    new_password = request.form.get('password')
    
    if not new_password:
        return "Password baru harus diisi", 400

    user = User.query.filter_by(reset_token=token).first()
    
    if user and user.reset_token_expiration > datetime.utcnow():
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.reset_token = None
        user.reset_token_expiration = None
        db.session.commit()
        
        # Sebaiknya kembalikan ke halaman sukses, bukan hanya teks
        return "Password Anda berhasil diganti! Silakan login kembali."
    else:
        return "Link sudah kedaluwarsa atau tidak valid", 400

@auth_bp.route("/halaman-reset-password/<token>", methods=["GET"])
def halaman_reset_password(token):
    """Tampilan form reset password untuk URL khusus halaman."""
    user = User.query.filter_by(reset_token=token).first()
    if user and user.reset_token_expiration > datetime.utcnow():
        return render_template("reset_password_form.html", token=token)
    else:
        return "Token tidak valid atau sudah kedaluwarsa", 400