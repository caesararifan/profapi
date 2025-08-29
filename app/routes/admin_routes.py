from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.models import(Event,EventTable, EventTableStatus, 
                       Table, Product, PaymentStatus, 
                       Ticket, Reservation, User)
import uuid
from app import db
from app import db
from app.utils import require_api_key, require_admin_role
from datetime import datetime
import os
import json
from werkzeug.utils import secure_filename

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
    """
    Endpoint untuk admin membuat event baru dengan upload gambar via form-data.
    Termasuk validasi untuk mencegah meja yang sama digunakan di banyak event.
    """
    # --- 1. Validasi Input Form ---
    if 'name' not in request.form or 'event_date' not in request.form:
        return jsonify({"error": "Field 'name' dan 'event_date' wajib diisi."}), 400

    # --- 2. Ambil dan Proses Data ---
    name = request.form.get('name')
    description = request.form.get('description')
    event_date_str = request.form.get('event_date')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    table_ids_str = request.form.get('table_ids')

    # Proses parsing tanggal dan waktu
    try:
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
        start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%H:%M:%S').time()
    except (ValueError, TypeError):
        return jsonify({"error": "Format tanggal atau waktu tidak valid. Gunakan 'YYYY-MM-DD' dan 'HH:MM:SS'."}), 400

    # Proses parsing table_ids
    table_ids = []
    if table_ids_str:
        try:
            table_ids = json.loads(table_ids_str)
            if not isinstance(table_ids, list): raise ValueError()
        except (json.JSONDecodeError, ValueError):
            return jsonify({"error": "Format table_ids tidak valid. Harus berupa array JSON dalam bentuk string, contoh: '[1, 2, 3]'"}), 400

    # --- 3. Proses Upload Gambar (Opsional) ---
    image_url = None
    if 'image' in request.files and request.files['image'].filename != '':
        image_file = request.files['image']
        if allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = current_app.config['UPLOAD_FOLDERS'].get('events')
            
            if not upload_folder:
                return jsonify({"error": "Konfigurasi folder upload untuk event tidak diatur."}), 500
            
            save_path = os.path.join(upload_folder, unique_filename)
            try:
                os.makedirs(upload_folder, exist_ok=True)
                image_file.save(save_path)
                image_url = f"/static/event_images/{unique_filename}"
            except Exception as e:
                current_app.logger.error(f"Gagal menyimpan file gambar event: {e}")
                return jsonify({"error": f"Tidak dapat menyimpan file di server: {e}"}), 500
        else:
            return jsonify({"error": "Tipe file gambar tidak diizinkan."}), 400

    # --- 4. Simpan ke Database dengan Transaksi ---
    try:
        # Buat objek Event
        new_event = Event(
            name=name,
            description=description,
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            is_active=True,
            image_url=image_url
        )
        db.session.add(new_event)
        db.session.flush()  # Diperlukan untuk mendapatkan new_event.id

        # Tautkan meja jika ada
        if table_ids:
            for tid in table_ids:
                table = Table.query.get(tid)
                if table:
                    # VALIDASI KUNCI: Cek apakah meja sudah terhubung ke event lain
                    existing_link = EventTable.query.filter_by(table_id=tid).first()
                    if existing_link:
                        # Jika sudah ada, batalkan seluruh transaksi dan kirim error
                        db.session.rollback()
                        return jsonify({
                            "error": "Conflict: Table already assigned.",
                            "message": f"Meja '{table.name}' (ID: {tid}) sudah digunakan di event lain dan tidak bisa ditambahkan."
                        }), 409  # 409 Conflict adalah status yang tepat

                    # Jika aman, buat hubungan baru
                    event_table = EventTable(
                        event_id=new_event.id,
                        table_id=tid,
                        status=EventTableStatus.AVAILABLE
                    )
                    db.session.add(event_table)
        
        # Jika semua validasi berhasil, simpan permanen
        db.session.commit()
        
        # --- 5. Siapkan dan Kirim Respons Sukses ---
        event_data = {
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
        return jsonify({
            "message": "Event berhasil dibuat!",
            "event": event_data
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal total saat membuat event: {e}")
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
    """Endpoint untuk admin membuat produk baru dengan upload gambar."""
    current_app.logger.info("--- Endpoint /products [POST] dipanggil ---")
    
    # 1. Validasi Input Dasar
    if 'name' not in request.form or 'price' not in request.form or 'stock' not in request.form:
        current_app.logger.warning("Request GAGAL: Field wajib (name, price, stock) tidak ada.")
        return jsonify({"error": "Field name, price, dan stock wajib ada"}), 400

    # 2. Ambil Data dari Form
    name = request.form.get('name')
    description = request.form.get('description')
    price_str = request.form.get('price')
    stock_str = request.form.get('stock')
    current_app.logger.info(f"Data Form Diterima: name='{name}', price='{price_str}', stock='{stock_str}'")

    # Validasi tipe data untuk price dan stock
    try:
        price = int(price_str)
        stock = int(stock_str)
    except (ValueError, TypeError):
        current_app.logger.warning("Request GAGAL: Price atau Stock bukan angka yang valid.")
        return jsonify({"error": "Price dan Stock harus berupa angka."}), 400

    # 3. Proses Upload Gambar
    image_url = None
    if 'image' in request.files and request.files['image'].filename != '':
        image_file = request.files['image']
        current_app.logger.info(f"File diterima: {image_file.filename}")
        
        if allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = current_app.config['UPLOAD_FOLDERS'].get('products')

            if not upload_folder:
                current_app.logger.error("FATAL: Konfigurasi 'products' di UPLOAD_FOLDERS tidak ditemukan!")
                return jsonify({"error": "Konfigurasi upload folder server bermasalah."}), 500

            save_path = os.path.join(upload_folder, unique_filename)
            current_app.logger.info(f"Mencoba menyimpan file ke: {save_path}")

            try:
                os.makedirs(upload_folder, exist_ok=True)
                image_file.save(save_path) # Poin kritis
                image_url = f"/static/product_images/{unique_filename}"
                current_app.logger.info("File berhasil disimpan.")
            except Exception as e:
                current_app.logger.error(f"GAGAL MENYIMPAN FILE! Error: {e}")
                return jsonify({"error": f"Tidak dapat menyimpan file di server. Detail: {e}"}), 500
        else:
            current_app.logger.warning("Upload GAGAL: Tipe file tidak diizinkan.")
            return jsonify({"error": "Tipe file tidak diizinkan."}), 400
    else:
        current_app.logger.info("Tidak ada file gambar yang diunggah, melanjutkan tanpa gambar.")

    # 4. Simpan ke Database
    try:
        current_app.logger.info("Mencoba menyimpan data produk ke database...")
        new_product = Product(
            name=name,
            description=description,
            price=price,
            stock=stock,
            image_url=image_url
        )
        db.session.add(new_product)
        db.session.commit()
        current_app.logger.info(f"Produk '{name}' berhasil disimpan dengan ID: {new_product.id}")

        return jsonify({
            "message": "Produk berhasil ditambahkan",
            "product": {
                "id": new_product.id,
                "name": new_product.name,
                "price": new_product.price,
                "stock": new_product.stock,
                "image_url": new_product.image_url
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"GAGAL COMMIT KE DATABASE! Error: {e}")
        return jsonify({"error": "Terjadi kesalahan pada database server."}), 500

@admin_bp.route("/products", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_all_products_admin():
    """Endpoint untuk admin melihat semua produk."""
    products = Product.query.all()
    return jsonify([
        {
            "id": p.id, 
            "name": p.name, 
            "description": p.description, 
            "price": p.price, 
            "stock": p.stock,
            "image_url": p.image_url # Menambahkan image_url di sini
        }
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
    reservation = Reservation.query.get_or_404(reservation_id)
    
    if reservation.payment_status == PaymentStatus.PAID:
        return jsonify({"message": "Reservasi ini sudah lunas."}), 400

    try:
        # 1. Ubah status reservasi
        reservation.payment_status = PaymentStatus.PAID

        # 2. Buat tiket untuk user
        event = reservation.event_table.event
        new_ticket = Ticket(
            ticket_code=f"TIX-{uuid.uuid4().hex[:10].upper()}",
            user_id=reservation.user_id,
            # Menggunakan getattr untuk keamanan jika invoice_id tidak ada
            invoice_id=getattr(reservation, 'invoice_id', None),
            event_id=event.id,
            # --- PERBAIKAN DI SINI ---
            expires_at=datetime.combine(event.event_date, event.end_time)
        )
        db.session.add(new_ticket)
        
        # Opsi untuk mengirim email notifikasi tiket bisa ditambahkan di sini
        
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
    
@admin_bp.route("/products/<int:id>", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_product(id):
    """Endpoint untuk admin melihat detail satu produk berdasarkan ID."""
    product = Product.query.get_or_404(id)
    
    return jsonify({
        "id": product.id, 
        "name": product.name, 
        "description": product.description, 
        "price": product.price, 
        "stock": product.stock,
        "image_url": product.image_url
    })

# DELETE untuk Product
@admin_bp.route("/products/<int:id>", methods=["DELETE"])
@require_api_key
@jwt_required()
@require_admin_role
def delete_product(id):
    """Endpoint untuk admin menghapus produk."""
    product = Product.query.get_or_404(id)
    
    if product.image_url:
        try:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDERS']['products'], os.path.basename(product.image_url))
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            current_app.logger.error(f"Gagal menghapus file gambar: {e}")

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": f"Produk '{product.name}' berhasil dihapus"})

# UPDATE untuk Event
@admin_bp.route("/events/<int:id>", methods=["PUT"])
@require_api_key
@jwt_required()
@require_admin_role
def update_event(id):
    """Endpoint untuk admin memperbarui detail event."""
    event = Event.query.get_or_404(id)
    data = request.get_json()

    # Update atribut dasar event
    event.name = data.get('name', event.name)
    event.description = data.get('description', event.description)
    event.is_active = data.get('is_active', event.is_active)

    # Update tanggal dan waktu jika ada
    if 'event_date' in data:
        event.event_date = datetime.strptime(data['event_date'], '%Y-%m-%d')
    if 'start_time' in data:
        event.start_time = datetime.strptime(data['start_time'], '%H:%M:%S').time()
    if 'end_time' in data:
        event.end_time = datetime.strptime(data['end_time'], '%H:%M:%S').time()

    # Update relasi meja (logika yang lebih kompleks)
    if 'table_ids' in data:
        new_table_ids = set(data['table_ids'])
        
        # Hapus relasi yang tidak ada lagi
        for event_table in list(event.event_tables):
            if event_table.table_id not in new_table_ids:
                db.session.delete(event_table)
        
        # Tambah relasi baru
        current_table_ids = {et.table_id for et in event.event_tables}
        for table_id in new_table_ids:
            if table_id not in current_table_ids:
                table = Table.query.get(table_id)
                if table:
                    new_event_table = EventTable(
                        event_id=event.id,
                        table_id=table_id,
                        status=EventTableStatus.AVAILABLE
                    )
                    db.session.add(new_event_table)

    db.session.commit()
    return jsonify({"message": f"Event '{event.name}' berhasil diperbarui"})

# DELETE untuk Event
@admin_bp.route("/events/<int:id>", methods=["DELETE"])
@require_api_key
@jwt_required()
@require_admin_role
def delete_event(id):
    """Endpoint untuk admin menghapus event."""
    event = Event.query.get_or_404(id)
    
    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": f"Event '{event.name}' berhasil dihapus"})

@admin_bp.route("/tables/available", methods=["GET"])
@require_api_key
@jwt_required()
@require_admin_role
def get_available_tables():
    """
    Endpoint untuk admin melihat daftar meja yang BELUM terikat
    ke event manapun.
    """
    try:
        # 1. Ambil semua ID meja yang sudah terikat di tabel EventTable
        used_table_ids_query = db.session.query(EventTable.table_id).distinct()
        used_table_ids = [id[0] for id in used_table_ids_query.all()]

        # 2. Ambil semua meja yang ID-nya TIDAK ADA dalam daftar ID yang sudah terikat
        available_tables = Table.query.filter(Table.id.notin_(used_table_ids)).all()

        # 3. Format respons JSON
        return jsonify([
            {
                "id": t.id,
                "name": t.name,
                "type": t.type,
                "capacity": t.capacity,
                "price": t.price
            } for t in available_tables
        ])

    except Exception as e:
        current_app.logger.error(f"Gagal mengambil meja yang tersedia: {e}")
        return jsonify({"error": "Terjadi kesalahan pada server."}), 500
    
@admin_bp.route("/users/<string:user_id>/reservations", methods=["DELETE"])
@require_api_key
@jwt_required()
@require_admin_role
def delete_all_user_reservations(user_id):
    """
    Endpoint ADMIN ONLY untuk menghapus SEMUA reservasi milik seorang pengguna.
    OPERASI INI BERSIFAT DESTRUKTIF DAN PERMANEN.
    """
    # 1. Pastikan pengguna ada
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Pengguna tidak ditemukan."}), 404

    # 2. Ambil semua reservasi milik pengguna tersebut
    reservations_to_delete = Reservation.query.filter_by(user_id=user_id).all()

    if not reservations_to_delete:
        return jsonify({"message": f"Tidak ada reservasi yang ditemukan untuk pengguna '{user.name}'."}), 200

    try:
        # 3. Lakukan proses penghapusan untuk setiap reservasi
        for reservation in reservations_to_delete:
            # Kembalikan stok produk yang dipesan
            for item in reservation.order_items:
                item.product.stock += item.quantity
            
            # Ubah status meja kembali menjadi AVAILABLE (jika belum lewat)
            if reservation.event_table.event.event_date >= datetime.utcnow().date():
                 reservation.event_table.status = EventTableStatus.AVAILABLE

            # Hapus tiket yang terhubung (jika ada)
            Ticket.query.filter_by(reservation_id=reservation.id).delete()

            # Hapus reservasi itu sendiri
            # (Penghapusan OrderItem akan otomatis jika cascade diatur di model)
            db.session.delete(reservation)

        # 4. Commit semua perubahan ke database
        db.session.commit()
        
        return jsonify({
            "message": f"Berhasil menghapus {len(reservations_to_delete)} reservasi milik pengguna '{user.name}'."
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal menghapus semua reservasi untuk user {user_id}: {e}")
        return jsonify({"error": "Terjadi kesalahan pada server saat proses penghapusan."}), 500