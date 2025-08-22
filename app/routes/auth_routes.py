from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_mail import Message
from flask_jwt_extended import create_access_token
from xendit import Xendit, XenditError
from ..models import User, Invoice, Ticket
import qrcode
import os
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

@auth_bp.route("/register/user", methods=["POST"]) # PERBAIKAN: Menambahkan .route
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
    # Coba ambil data dari JSON
    data = request.get_json()
    email = None
    
    if data:
        email = data.get('email')
    else:
        # Kalau tidak ada JSON, coba dari form biasa
        email = request.form.get('email')
    
    # Validasi email
    if not email:
        return "Email harus diisi", 400  # Kembalikan error jika email kosong

    # Cari user berdasarkan email
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
                sender=current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME'),
                recipients=[user.email]
            )
            msg.body = f"Halo {user.name},\n\nKlik link ini untuk reset password:\n{reset_link}\n\nLink berlaku 1 jam."
            mail.send(msg)
            
            current_app.logger.info(f"Email reset password dikirim ke {user.email}")
            
        except Exception as e:
            current_app.logger.error(f"GAGAL KIRIM EMAIL: {str(e)}")
            return f"Error mengirim email: {str(e)}", 500
        
        return "Link reset sudah dikirim ke email Anda"
    else:
        return "Email tidak ditemukan", 404

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
        
        return ("Password Anda Berhasil Diganti!!")
    else:
        return "Link sudah kadaluarsa atau tidak valid", 400

@auth_bp.route("/halaman-reset-password/<token>", methods=["GET"])
def halaman_reset_password(token):
    """Tampilan form reset password untuk URL khusus halaman."""
    user = User.query.filter_by(reset_token=token).first()
    if user and user.reset_token_expiration > datetime.utcnow():
        return render_template("reset_password_form.html", token=token)
    else:
        return "Token tidak valid atau sudah kedaluwarsa", 400

def create_xendit_invoice(amount, description, payer_email):
    """Fungsi bantuan untuk membuat invoice di Xendit menggunakan SDK."""
    try:
        xendit_instance = Xendit(api_key=current_app.config['XENDIT_API_KEY'])
        external_id = f"invoice-flask-{uuid.uuid4()}"
        
        created_invoice = xendit_instance.Invoice.create(
            external_id=external_id,
            payer_email=payer_email,
            description=description,
            amount=amount
        )
        return created_invoice, None
    except XenditError as e:
        return None, f"Error dari Xendit: {e.error_code}"
    except Exception as e:
        return None, f"Terjadi kesalahan tak terduga: {e}"

@auth_bp.route("/xendit-webhook", methods=["POST"])
def xendit_webhook():
    """
    Endpoint untuk menerima callback dari Xendit, memperbarui status,
    dan mengirimkan BUKTI PEMBAYARAN / E-TIKET jika pembayaran berhasil.
    """
    callback_token = request.headers.get('x-callback-token')
    # Sesuaikan dengan nama variabel di config.py jika berbeda
    if callback_token != current_app.config['XENDIT_WEBHOOK_VERIFICATION_TOKEN']:
        current_app.logger.warning("Webhook dengan callback token tidak valid diterima.")
        return jsonify({"error": "Invalid callback token"}), 403

    data = request.get_json()
    current_app.logger.info(f"Webhook diterima dari Xendit: {data}")

    try:
        invoice_external_id = data.get('external_id')
        invoice_status = data.get('status')

        invoice_to_update = Invoice.query.filter_by(external_id=invoice_external_id).first()

        if not invoice_to_update:
            current_app.logger.warning(f"Invoice dengan external_id {invoice_external_id} tidak ditemukan.")
            return jsonify({"status": "ok", "message": "Invoice not found"}), 200

        invoice_to_update.status = invoice_status
        db.session.commit()
        current_app.logger.info(f"Status invoice {invoice_external_id} diperbarui menjadi {invoice_status}")

        if invoice_status == 'PAID' and not invoice_to_update.ticket:
            event = invoice_to_update.event
            
            new_ticket = Ticket(
                ticket_code=secrets.token_hex(16),
                invoice_id=invoice_to_update.id,
                user_id=invoice_to_update.user_id,
                event_id=event.id,
                expires_at=event.event_date
            )
            db.session.add(new_ticket)
            db.session.commit()
            current_app.logger.info(f"Tiket {new_ticket.ticket_code} berhasil dibuat untuk event '{event.name}'")

            # Buat gambar QR Code
            qr_img = qrcode.make(new_ticket.ticket_code)
            qr_code_dir = os.path.join(current_app.root_path, 'static', 'qrcodes')
            os.makedirs(qr_code_dir, exist_ok=True)
            qr_image_path = os.path.join(qr_code_dir, f'{new_ticket.ticket_code}.png')
            qr_img.save(qr_image_path)

            # --- PERUBAHAN UTAMA: Konten Email Dibuat Lebih Detail ---
            
            # Format tanggal dan harga agar lebih rapi
            payment_date = datetime.now().strftime('%d %B %Y, %H:%M:%S WIB')
            formatted_price = "Rp {:,}".format(event.price).replace(',', '.')

            msg = Message(
                subject=f"Bukti Pembayaran & E-Tiket untuk {event.name}",
                recipients=[invoice_to_update.user.email]
            )
            msg.html = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2>Halo {invoice_to_update.user.name},</h2>
                <p>Terima kasih! Pembayaran Anda telah berhasil kami terima.</p>
                
                <h3>Detail Invoice</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 8px;">No. Invoice</td>
                        <td style="padding: 8px;">: <strong>{invoice_to_update.external_id}</strong></td>
                    </tr>
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 8px;">Tanggal Pembayaran</td>
                        <td style="padding: 8px;">: {payment_date}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 8px;">Item</td>
                        <td style="padding: 8px;">: Tiket untuk <strong>{event.name}</strong></td>
                    </tr>
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 8px;">Jumlah</td>
                        <td style="padding: 8px;">: <strong>{formatted_price}</strong></td>
                    </tr>
                </table>

                <hr>

                <h3>E-Tiket Anda</h3>
                <p>Berikut adalah E-Tiket Anda. Silakan tunjukkan QR Code ini kepada petugas kami di lokasi.</p>
                <p>Kode Tiket: <strong>{new_ticket.ticket_code}</strong></p>
                <p><i>QR Code terlampir dalam email ini.</i></p>
            </div>
            """
            
            # Lampirkan QR code ke email
            with current_app.open_resource(qr_image_path) as fp:
                msg.attach(f"{new_ticket.ticket_code}.png", "image/png", fp.read())
            
            mail.send(msg)
            current_app.logger.info(f"Email E-Tiket dikirim ke {invoice_to_update.user.email}")

            # Opsional: Hapus file QR code dari server setelah dikirim
            # os.remove(qr_image_path)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error memproses webhook Xendit: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "success"}), 200