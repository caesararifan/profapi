from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import (
    Reservation, EventTable, EventTableStatus, PaymentStatus, 
    Ticket, Event, User, Product, OrderItem
)
from app import db
import urllib.parse
import uuid
from datetime import datetime

reservation_bp = Blueprint('reservation', __name__, url_prefix='/reservations')

@reservation_bp.route("/", methods=["POST"])
@jwt_required()
def create_reservation():
    """
    Endpoint untuk membuat reservasi meja DAN memesan produk.
    Fungsi ini sekarang akan menghasilkan URL WhatsApp untuk pembayaran manual.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body cannot be empty."}), 400

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    # --- 1. VALIDASI INPUT ---
    event_table_id = data.get('event_table_id')
    number_of_guests = data.get('number_of_guests')
    arrival_time_str = data.get('arrival_time')
    order_items_data = data.get('order_items', [])

    if not isinstance(event_table_id, int):
        return jsonify({"error": "event_table_id is required and must be an integer."}), 400
    if not isinstance(number_of_guests, int) or number_of_guests <= 0:
        return jsonify({"error": "number_of_guests is required and must be a positive integer."}), 400
    if not isinstance(order_items_data, list):
        return jsonify({"error": "order_items must be a list."}), 400

    arrival_time = None
    if arrival_time_str:
        try:
            arrival_time = datetime.strptime(arrival_time_str, '%H:%M:%S').time()
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid format for arrival_time. Use 'HH:MM:SS'."}), 400

    # --- 2. VALIDASI DATABASE DAN LOCKING ---
    event_table = db.session.query(EventTable).filter_by(id=event_table_id).with_for_update().first()
    
    if not event_table:
        return jsonify({"error": "The selected table for this event does not exist."}), 404
    if event_table.status != EventTableStatus.AVAILABLE:
        return jsonify({"error": "Sorry, this table is no longer available."}), 409
    if number_of_guests > event_table.table.capacity:
        return jsonify({
            "error": "Number of guests exceeds the table's capacity.",
            "table_capacity": event_table.table.capacity
        }), 400

    # --- 3. LOGIKA TRANSAKSI ---
    try:
        total_amount = event_table.table.price
        ordered_products_details = []
        
        for item in order_items_data:
            product = db.session.query(Product).filter_by(id=item['product_id']).with_for_update().first()
            if not product:
                raise ValueError(f"Product with ID {item['product_id']} not found.")
            if product.stock < item['quantity']:
                raise ValueError(f"Not enough stock for '{product.name}'. Available: {product.stock}, Requested: {item['quantity']}.")
            
            subtotal = product.price * item['quantity']
            total_amount += subtotal
            ordered_products_details.append(f"- {item['quantity']}x {product.name} (Rp {subtotal:,})")

        event_table.status = EventTableStatus.BOOKED

        new_reservation = Reservation(
            user_id=current_user_id,
            event_table_id=event_table_id,
            number_of_guests=number_of_guests,
            total_amount=total_amount,
            payment_status=PaymentStatus.WAITING_MANUAL_PAYMENT, 
            arrival_time=arrival_time
        )
        db.session.add(new_reservation)
        db.session.flush()

        for item in order_items_data:
            product = db.session.query(Product).get(item['product_id'])
            order_item = OrderItem(
                reservation_id=new_reservation.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                subtotal=product.price * item['quantity']
            )
            product.stock -= item['quantity']
            db.session.add(order_item)
            
        # --- LOGIKA PEMBAYARAN MANUAL VIA WHATSAPP ---
        admin_phone_number = current_app.config.get('ADMIN_WHATSAPP_NUMBER')
        if not admin_phone_number:
            raise ValueError("Nomor WhatsApp admin belum diatur di konfigurasi.")

        products_text = "\n".join(ordered_products_details) if ordered_products_details else "Tidak ada."

        message_text = f"""Halo Admin,\n\nSaya ingin menyelesaikan pembayaran untuk reservasi berikut:\n\n*ID Reservasi:* {new_reservation.id}\n*Nama Pemesan:* {user.name}\n*Event:* {event_table.event.name}\n*Meja:* {event_table.table.name}\n*Jumlah Tamu:* {number_of_guests} orang\n\n*Pesanan Tambahan:*\n{products_text}\n\n*Total Pembayaran: Rp {total_amount:,}*\n\nMohon informasikan langkah selanjutnya untuk transfer. Terima kasih."""
        encoded_message = urllib.parse.quote(message_text)
        whatsapp_url = f"https://wa.me/{admin_phone_number}?text={encoded_message}"
        
        db.session.commit()

        return jsonify({
            "message": "Reservasi berhasil dicatat. Silakan hubungi admin via WhatsApp untuk menyelesaikan pembayaran.",
            "reservation_id": new_reservation.id,
            "whatsapp_url": whatsapp_url
        }), 201

    except ValueError as ve:
        db.session.rollback()
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saat reservasi manual: {e}")
        return jsonify({"error": "Terjadi kesalahan internal server."}), 500

@reservation_bp.route("/my-reservations", methods=["GET"])
@jwt_required()
def get_my_reservations():
    """Endpoint untuk user melihat riwayat reservasi miliknya."""
    current_user_id = get_jwt_identity()
    
    reservations = Reservation.query.filter_by(user_id=current_user_id).order_by(Reservation.created_at.desc()).all()
    
    if not reservations:
        return jsonify([]), 200 # Kembalikan list kosong jika tidak ada

    results = []
    for res in reservations:
        results.append({
            "reservation_id": res.id,
            "event_name": res.event_table.event.name,
            "event_date": res.event_table.event.event_date.isoformat(),
            "table_name": res.event_table.table.name,
            "number_of_guests": res.number_of_guests,
            "total_amount": res.total_amount,
            "payment_status": res.payment_status.value,
            "reservation_date": res.created_at.isoformat()
        })
        
    return jsonify(results)

@reservation_bp.route("/my-tickets", methods=["GET"])
@jwt_required()
def get_my_tickets():
    """Endpoint untuk user melihat daftar tiket aktif miliknya."""
    current_user_id = get_jwt_identity()
    
    # Ambil tiket yang belum dipakai dan event-nya belum/sedang berlangsung
    active_tickets = Ticket.query.join(Ticket.event).filter(
        Ticket.user_id == current_user_id,
        Ticket.is_used == False,
        Event.event_date >= datetime.utcnow().date()
    ).order_by(Event.event_date.asc()).all()
    
    return jsonify([
        {
            "ticket_code": t.ticket_code,
            "event_name": t.event.name,
            "event_date": t.event.event_date.isoformat(),
            "is_used": t.is_used
        } for t in active_tickets
    ])