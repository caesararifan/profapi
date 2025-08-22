from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.models import Event,EventTable, EventTableStatus, Table, Product
from app import db
from app import db
from app.utils import require_api_key, require_admin_role
from datetime import datetime
# import uuid

# Membuat Blueprint baru untuk admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route("/")
def index():
    """Endpoint dasar untuk mengecek apakah API berjalan."""
    return jsonify({"status": "ok", "message": "API Anda berjalan dengan baik!"})

@admin_bp.route("/create-event", methods=["POST"])
@require_api_key
@jwt_required()
@require_admin_role
def create_event():
    """Endpoint untuk admin membuat event baru + generate table mapping."""
    data = request.get_json()
    
    name = data.get('name')
    description = data.get('description')  # opsional
    event_date_str = data.get('event_date')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    table_ids = data.get('table_ids')  # opsional, list table_id yang dipakai event

    # Validasi basic
    if not all([name, event_date_str, start_time_str, end_time_str]):
        return jsonify({"error": "Nama, tanggal, jam mulai, dan jam selesai diperlukan"}), 400

    # Parse tanggal
    try:
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return jsonify({"error": "Format tanggal tidak valid. Gunakan 'YYYY-MM-DD HH:MM:SS'"}), 400

    # Parse jam
    try:
        start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%H:%M:%S').time()
    except ValueError:
        return jsonify({"error": "Format waktu tidak valid. Gunakan 'HH:MM:SS'"}), 400

    # buat event baru
    new_event = Event(
        name=name,
        description=description,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        is_active=True  # default aktif
    )

    try:
        db.session.add(new_event)
        db.session.flush()  # supaya new_event.id bisa dipakai

        # Jika ada table_ids, buat event_table untuk tiap meja
        if table_ids and isinstance(table_ids, list):
            for tid in table_ids:
                event_table = EventTable(
                    event_id=new_event.id,
                    table_id=tid,
                    status=EventTableStatus.AVAILABLE
                )
                db.session.add(event_table)

        db.session.commit()
        
        return jsonify({
            "message": "Event berhasil dibuat!",
            "event": {
                "id": new_event.id,
                "name": new_event.name,
                "description": new_event.description,
                "event_date": new_event.event_date.isoformat(),
                "start_time": str(new_event.start_time),
                "end_time": str(new_event.end_time),
                "is_active": new_event.is_active,
                "tables": [
                    {
                        "table_id": et.table_id,
                        "status": et.status.value,
                        "price": et.table.price  # ambil harga dari table
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