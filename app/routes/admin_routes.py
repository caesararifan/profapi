from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.models import Event,EventTable, EventTableStatus, Table, Product, PaymentStatus, Ticket, Reservation
import uuid
from app import db
from app import db
from app.utils import require_api_key, require_admin_role
from datetime import datetime
import os
import json
from werkzeug.utils import secure_filename

# Membuat Blueprint baru untuk admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route("/")
def index():
    """Endpoint dasar untuk mengecek apakah API berjalan."""
    return jsonify({"status": "ok", "message": "API Anda berjalan dengan baik!"})

def allowed_file(filename):
    """Fungsi helper untuk memeriksa ekstensi file yang diizinkan."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@admin_bp.route("/create-event", methods=["POST"])
@require_api_key
@jwt_required()
@require_admin_role
def create_event():
    """Endpoint untuk admin membuat event baru dengan upload gambar via form-data."""
    
    # --- 1. Ambil Data dari Form ---
    # Memeriksa field wajib dari form
    if 'name' not in request.form or 'event_date' not in request.form:
        return jsonify({"error": "Field 'name' dan 'event_date' wajib diisi."}), 400

    name = request.form.get('name')
    description = request.form.get('description')
    event_date_str = request.form.get('event_date')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    table_ids_str = request.form.get('table_ids') # table_ids diterima sebagai string

    # --- 2. Proses Upload Gambar ---
    image_url = None
    if 'image' in request.files:
        image_file = request.files['image']
        # Pastikan file ada, punya nama, dan ekstensinya diizinkan
        if image_file and image_file.filename and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            
            upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if not upload_folder:
                 return jsonify({"error": "UPLOAD_FOLDER tidak diatur di konfigurasi."}), 500

            os.makedirs(upload_folder, exist_ok=True)
            
            save_path = os.path.join(upload_folder, unique_filename)
            image_file.save(save_path)
            
            # URL yang akan disimpan di database dan dikirim ke client
            image_url = f"/static/event_images/{unique_filename}"
            
    # --- 3. Validasi dan Parsing Data Teks ---
    if not all([name, event_date_str, start_time_str, end_time_str]):
        return jsonify({"error": "Nama, tanggal, jam mulai, dan jam selesai diperlukan"}), 400

    try:
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Format tanggal tidak valid. Gunakan 'YYYY-MM-DD'"}), 400

    try:
        start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%H:%M:%S').time()
    except ValueError:
        return jsonify({"error": "Format waktu tidak valid. Gunakan 'HH:MM:SS'"}), 400

    table_ids = []
    if table_ids_str:
        try:
            # Mengubah string '[1,2,3]' menjadi list [1, 2, 3]
            table_ids = json.loads(table_ids_str)
            if not isinstance(table_ids, list):
                raise ValueError()
        except (json.JSONDecodeError, ValueError):
            return jsonify({"error": "Format table_ids tidak valid. Harus berupa array JSON dalam bentuk string, contoh: '[1, 2, 3]'"}), 400

    # --- 4. Simpan ke Database ---
    new_event = Event(
        name=name,
        description=description,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        is_active=True,
        image_url=image_url # Menyimpan path gambar
    )

    try:
        db.session.add(new_event)
        db.session.flush() # Diperlukan untuk mendapatkan new_event.id

        # Membuat relasi EventTable jika table_ids diberikan
        if table_ids:
            for tid in table_ids:
                # Sebaiknya ada validasi apakah table_id (tid) benar-benar ada
                table = Table.query.get(tid)
                if table:
                    event_table = EventTable(
                        event_id=new_event.id,
                        table_id=tid,
                        status=EventTableStatus.AVAILABLE
                    )
                    db.session.add(event_table)
        
        db.session.commit()
        
        # --- 5. Kirim Response Sukses ---
        return jsonify({
            "message": "Event berhasil dibuat!",
            "event": {
                "id": new_event.id,
                "name": new_event.name,
                "description": new_event.description,
                "image_url": new_event.image_url,
                "event_date": new_event.event_date.strftime('%Y-%m-%d'),
                "start_time": new_event.start_time.strftime('%H:%M:%S'),
                "end_time": new_event.end_time.strftime('%H:%M:%S'),
                "is_active": new_event.is_active,
                "tables": [
                    {
                        "event_table_id": et.id,
                        "table_id": et.table_id,
                        "table_name": et.table.name,
                        "status": et.status.value,
                        "price": et.table.price
                    } for et in new_event.event_tables
                ]
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal membuat event: {e}")
        return jsonify({"error": "Terjadi kesalahan pada server saat menyimpan event."}), 500

@admin_bp.route("/events/<int:id>", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_event(id):
    """Endpoint untuk admin melihat detail satu event berdasarkan ID."""
    event = Event.query.get(id)
    if not event:
        return jsonify({
            "error": "Event not found",
            "message": f"Event dengan ID {id} tidak ditemukan."
        }), 404

    return jsonify({
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "event_date": event.event_date.isoformat(),
        "start_time": str(event.start_time),
        "end_time": str(event.end_time),
        "is_active": event.is_active,
        "tables": [
            {
                "event_table_id": et.id,
                "table_id": et.table_id,
                "status": et.status.value,
                "price": et.table.price   # ambil harga dari tabel
            } for et in event.event_tables
        ]
    })

# CREATE
@admin_bp.route("/tables", methods=["POST"])
@require_api_key
@jwt_required()
@require_admin_role
def create_table():
    data = request.get_json()

    # Validasi field wajib
    if not all(k in data for k in ["name", "type", "capacity", "price"]):
        return jsonify({"error": "Field name, type, capacity, dan price wajib ada"}), 400

    # Validasi harga
    if not isinstance(data["price"], int) or data["price"] < 0:
        return jsonify({"error": "Harga harus berupa integer positif"}), 400

    new_table = Table(
        name=data["name"],
        type=data["type"],
        capacity=data["capacity"],
        price=data["price"]
    )
    db.session.add(new_table)
    db.session.commit()

    return jsonify({
        "message": "Table created",
        "table": {
            "id": new_table.id,
            "name": new_table.name,
            "type": new_table.type,
            "capacity": new_table.capacity,
            "price": new_table.price
        }
    }), 201

# READ (all)
@admin_bp.route("/tables", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_tables():
    """Endpoint untuk admin melihat semua meja beserta harganya."""
    tables = Table.query.all()
    return jsonify([
        {
            "id": t.id,
            "name": t.name,
            "type": t.type,
            "capacity": t.capacity,
            "price": t.price
        } for t in tables
    ])


# READ (one)
@admin_bp.route("/tables/<int:id>", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_table(id):
    """Endpoint untuk admin melihat detail satu table berdasarkan ID."""
    table = Table.query.get(id)
    if not table:
        return jsonify({
            "error": "Table not found",
            "message": f"Table dengan ID {id} tidak ditemukan."
        }), 404

    return jsonify({
        "id": table.id,
        "name": table.name,
        "type": table.type,
        "capacity": table.capacity,
        "price":table.price
    })

# UPDATE
@admin_bp.route("/tables/<int:id>", methods=["PUT"])
@require_api_key
@jwt_required()
@require_admin_role
def update_table(id):
    table = Table.query.get_or_404(id)
    data = request.get_json()
    table.name = data.get("name", table.name)
    table.type = data.get("type", table.type)
    table.capacity = data.get("capacity", table.capacity)
    db.session.commit()
    return jsonify({"message": "Table updated"})

# DELETE
@admin_bp.route("/tables/<int:id>", methods=["DELETE"])
@require_api_key
@jwt_required()
@require_admin_role
def delete_table(id):
    table = Table.query.get_or_404(id)
    db.session.delete(table)
    db.session.commit()
    return jsonify({"message": "Table deleted"})

@admin_bp.route("/events", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_all_events():
    """Endpoint untuk admin melihat semua event yang pernah dibuat."""
    # Ambil semua event, urutkan berdasarkan tanggal event terbaru
    events = Event.query.order_by(Event.event_date.desc()).all()
    
    # Siapkan list untuk menampung hasil
    events_list = []
    
    # Loop setiap event untuk memformat output JSON
    for event in events:
        event_data = {
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "event_date": event.event_date.isoformat(),
            "start_time": event.start_time.strftime('%H:%M:%S'),
            "end_time": event.end_time.strftime('%H:%M:%S'),
            "is_active": event.is_active,
            "tables": [
                {
                    "event_table_id": et.id,
                    "table_id": et.table_id,
                    "table_name": et.table.name, # Tambahkan nama meja agar lebih jelas
                    "status": et.status.value,
                    "price": et.table.price
                } for et in event.event_tables
            ]
        }
        events_list.append(event_data)
        
    return jsonify(events_list)

@admin_bp.route("/products", methods=["POST"])
@require_api_key
@jwt_required()
@require_admin_role
def create_product():
    """Endpoint untuk admin membuat produk baru."""
    data = request.get_json()
    if not all(k in data for k in ["name", "price", "stock"]):
        return jsonify({"error": "Field name, price, dan stock wajib ada"}), 400

    new_product = Product(
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        stock=data["stock"]
    )
    db.session.add(new_product)
    db.session.commit()
    return jsonify({
        "message": "Produk berhasil ditambahkan",
        "product": {"id": new_product.id, "name": new_product.name, "price": new_product.price}
    }), 201

@admin_bp.route("/products", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_all_products_admin():
    """Endpoint untuk admin melihat semua produk."""
    products = Product.query.all()
    return jsonify([
        {"id": p.id, "name": p.name, "description": p.description, "price": p.price, "stock": p.stock}
        for p in products
    ])

@admin_bp.route("/products/<int:id>", methods=["PUT"])
@require_api_key
@jwt_required()
@require_admin_role
def update_product(id):
    """Endpoint untuk admin memperbarui produk."""
    product = Product.query.get_or_404(id)
    data = request.get_json()
    product.name = data.get("name", product.name)
    product.description = data.get("description", product.description)
    product.price = data.get("price", product.price)
    product.stock = data.get("stock", product.stock)
    db.session.commit()
    return jsonify({"message": "Produk berhasil diperbarui"})

@admin_bp.route("/reservations/<int:reservation_id>/confirm-payment", methods=["POST"])
@require_api_key
@jwt_required()
@require_admin_role
def confirm_manual_payment(reservation_id):
    """
    Endpoint KHUSUS ADMIN untuk mengonfirmasi pembayaran manual 
    dan men-trigger pembuatan tiket.
    """
    reservation = Reservation.query.get(reservation_id)
    if not reservation:
        return jsonify({"error": "Reservasi tidak ditemukan."}), 404
    
    if reservation.payment_status == PaymentStatus.PAID:
        return jsonify({"message": "Reservasi ini sudah lunas."}), 400

    try:
        # 1. Ubah status reservasi
        reservation.payment_status = PaymentStatus.PAID

        # 2. Buat tiket untuk user (logika yang sebelumnya ada di webhook)
        event = reservation.event_table.event
        new_ticket = Ticket(
            ticket_code=f"TIX-{uuid.uuid4().hex[:10].upper()}",
            user_id=reservation.user_id,
            invoice_id=reservation.invoice_id, # invoice_id mungkin null jika tidak dibuat
            event_id=event.id,
            expires_at=datetime.combine(event.event_date.date(), event.end_time)
        )
        db.session.add(new_ticket)
        
        # (Opsional) Kirim email konfirmasi dan e-tiket ke user di sini
        # Anda bisa memindahkan logika pengiriman email dari webhook Xendit ke sini
        # current_app.logger.info(f"Mengirim email tiket {new_ticket.ticket_code} ke user {reservation.user.email}")
        
        db.session.commit()
        
        return jsonify({
            "message": "Pembayaran berhasil dikonfirmasi!",
            "reservation_id": reservation.id,
            "new_status": "PAID",
            "ticket_code_created": new_ticket.ticket_code
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal konfirmasi pembayaran manual: {e}")
        return jsonify({"error": "Terjadi kesalahan pada server."}), 500