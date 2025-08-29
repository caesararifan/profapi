from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from datetime import datetime
# import uuid
from ..models import User, Invoice, Event, Ticket, Table, Product
from .. import db
from ..utils import require_api_key

# Membuat Blueprint baru untuk user
user_bp = Blueprint('user', __name__)

# FUNGSI DAN ROUTE XENDIT DIHAPUS DARI SINI

@user_bp.route("/my-tickets", methods=["GET"])
@require_api_key
@jwt_required()
def get_my_tickets():
    """Endpoint untuk user di Flutter meminta daftar tiket aktif mereka."""
    # Disarankan untuk menggunakan get_jwt_identity() untuk keamanan
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id diperlukan"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User tidak ditemukan"}), 404

    active_tickets = db.session.query(Ticket).join(Invoice).filter(
        Ticket.user_id == user.id,
        Invoice.status == 'PAID',
        Ticket.expires_at > datetime.utcnow()
    ).all()

    if not active_tickets:
        return jsonify({"tickets": []})

    tickets_data = []
    for ticket in active_tickets:
        # Asumsi qrcode sudah digenerate sebelumnya dan disimpan dengan nama ticket_code.png
        qr_code_url = f"{request.host_url}static/qrcodes/{ticket.ticket_code}.png"
        
        tickets_data.append({
            "ticket_code": ticket.ticket_code,
            "event_name": ticket.event.name,
            "qr_code_url": qr_code_url,
            "expires_at": ticket.expires_at.isoformat()
        })

    return jsonify({"tickets": tickets_data})


@user_bp.route("/tables", methods=["GET"])
@require_api_key
@jwt_required()
def user_get_tables():
    """Endpoint untuk user melihat daftar semua meja."""
    tables = Table.query.all()
    return jsonify([
        {"id": t.id, "name": t.name, "type": t.type, "capacity": t.capacity}
        for t in tables
    ])


@user_bp.route("/events", methods=["GET"])
@require_api_key
@jwt_required()
def user_get_events():
    """Endpoint untuk user melihat daftar event yang aktif."""
    events = Event.query.filter_by(is_active=True).all()
    return jsonify([
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "event_date": e.event_date.isoformat(),
            "start_time": str(e.start_time),
            "end_time": str(e.end_time),
            # "price": e.price # Anda mungkin ingin menyesuaikan cara harga ditampilkan
        }
        for e in events
    ])


@user_bp.route("/events/<int:event_id>", methods=["GET"])
@require_api_key
@jwt_required()
def user_get_event_detail(event_id):
    """Endpoint untuk user melihat detail satu event beserta meja yang tersedia."""
    event = Event.query.get_or_404(event_id)
    
    # Menambahkan detail gambar dari event itu sendiri
    event_image_url = event.image_url if event.image_url else None

    return jsonify({
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "image_url": event_image_url, # <-- Menampilkan gambar event
        "event_date": event.event_date.isoformat(),
        "start_time": str(event.start_time),
        "end_time": str(event.end_time),
        "tables": [
            {
                # ID unik untuk hubungan event-meja, ini yang dikirim saat reservasi
                "event_table_id": et.id, 
                "table_id": et.table.id,
                "table_name": et.table.name,       # <-- Detail tambahan
                "table_capacity": et.table.capacity, # <-- Detail tambahan
                "table_price": et.table.price,       # <-- Detail tambahan
                "status": et.status.value
            }
            for et in event.event_tables
        ]
    })

@user_bp.route("/products", methods=["GET"])
@require_api_key
@jwt_required()
def user_get_products():
    """Endpoint untuk user melihat semua produk yang tersedia."""
    try:
        products = Product.query.filter(Product.stock > 0).all()
        
        products_list = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": p.price,
                "stock": p.stock,
                "image_url": p.image_url
            }
            for p in products
        ]
        
        return jsonify(products_list)
        
    except Exception as e:
        current_app.logger.error(f"Gagal mengambil data produk: {e}")
        return jsonify({"error": "Terjadi kesalahan pada server saat mengambil data produk."}), 500