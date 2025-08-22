from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Reservation, EventTable, EventTableStatus, PaymentStatus, Invoice, Ticket, Event, InvoiceStatus, User, Product, OrderItem
from app import db
from xendit import Xendit, XenditError
import uuid
from datetime import datetime

reservation_bp = Blueprint('reservation', __name__, url_prefix='/reservations')

@reservation_bp.route("/", methods=["POST"])
@jwt_required()
def create_reservation():
    """
    Endpoint for creating a table reservation AND ordering products (OrderItems).
    This function immediately creates a Xendit invoice and returns the payment URL.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body cannot be empty."}), 400

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        # This case is unlikely if the JWT is valid, but it's a good safeguard.
        return jsonify({"error": "User not found."}), 404

    # --- 1. INPUT VALIDATION ---
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

    # --- 2. DATABASE VALIDATION AND LOCKING ---
    # Use with_for_update() to lock the row during the transaction to prevent race conditions (double-booking).
    event_table = db.session.query(EventTable).filter_by(id=event_table_id).with_for_update().first()
    
    if not event_table:
        return jsonify({"error": "The selected table for this event does not exist."}), 404
    if event_table.status != EventTableStatus.AVAILABLE:
        return jsonify({"error": "Sorry, this table is no longer available."}), 409 # 409 Conflict is appropriate here
    if number_of_guests > event_table.table.capacity:
        return jsonify({
            "error": "Number of guests exceeds the table's capacity.",
            "table_capacity": event_table.table.capacity
        }), 400

    # --- 3. TRANSACTIONAL LOGIC ---
    try:
        # --- Calculate Total Price ---
        total_amount = event_table.table.price
        
        # Validate products and calculate subtotal
        for item in order_items_data:
            if not all(k in item for k in ['product_id', 'quantity']):
                 raise ValueError("Each item in order_items must have 'product_id' and 'quantity'.")
            
            product = db.session.query(Product).filter_by(id=item['product_id']).with_for_update().first()
            if not product:
                raise ValueError(f"Product with ID {item['product_id']} not found.")
            if product.stock < item['quantity']:
                raise ValueError(f"Not enough stock for '{product.name}'. Available: {product.stock}, Requested: {item['quantity']}.")
            
            total_amount += product.price * item['quantity']
        
        # --- Create Reservation and Order Items ---
        event_table.status = EventTableStatus.BOOKED

        # Create the main reservation record
        new_reservation = Reservation(
            user_id=current_user_id,
            event_table_id=event_table_id,
            number_of_guests=number_of_guests,
            total_amount=total_amount,
            payment_status=PaymentStatus.PENDING,
            arrival_time=arrival_time
        )
        db.session.add(new_reservation)
        db.session.flush() # Flush to get the new_reservation.id

        # Create OrderItem records for each product and update stock
        for item in order_items_data:
            product = db.session.query(Product).get(item['product_id']) # Re-fetch to ensure it's in the session
            order_item = OrderItem(
                reservation_id=new_reservation.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                subtotal=product.price * item['quantity']
            )
            product.stock -= item['quantity'] # Decrease product stock
            db.session.add(order_item)
        
        # --- Create Invoice and Link to Xendit ---
        invoice = Invoice(
            user_id=current_user_id,
            amount=total_amount,
            status=InvoiceStatus.PENDING
        )
        db.session.add(invoice)
        db.session.flush() # Flush to get the invoice.id

        new_reservation.invoice_id = invoice.id
        external_id = f"invoice-{invoice.id}-{uuid.uuid4().hex[:6]}"
        invoice.external_id = external_id

        # Call Xendit API
        xendit_instance = Xendit(api_key=current_app.config['XENDIT_API_KEY'])
        created_invoice = xendit_instance.Invoice.create(
            external_id=external_id,
            payer_email=user.email,
            description=f"Reservation for {event_table.event.name} - Table {event_table.table.name}",
            amount=total_amount,
            # You can add more details here if needed
            # success_redirect_url="your-app://payment-success",
            # failure_redirect_url="your-app://payment-failure"
        )
        
        invoice.invoice_url = created_invoice.invoice_url
        db.session.commit() # Commit the entire transaction

        return jsonify({
            "message": "Reservation created successfully! Please proceed to payment.",
            "invoice_url": created_invoice.invoice_url
        }), 201

    except ValueError as ve:
        db.session.rollback()
        return jsonify({"error": str(ve)}), 400
    except XenditError as xe:
        db.session.rollback()
        current_app.logger.error(f"Xendit API Error: {xe}")
        return jsonify({"error": "Failed to create payment invoice.", "details": str(xe)}), 502 # Bad Gateway
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"An unexpected error occurred during reservation: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@reservation_bp.route("/my-reservations", methods=["GET"])
@jwt_required()
def get_my_reservations():
    """Endpoint untuk user melihat riwayat reservasi miliknya."""
    current_user_id = get_jwt_identity()
    
    reservations = Reservation.query.filter_by(user_id=current_user_id).order_by(Reservation.created_at.desc()).all()
    
    if not reservations:
        return jsonify({"message": "Anda belum memiliki reservasi."}), 200

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

@reservation_bp.route("/xendit-webhook", methods=["POST"])
def xendit_webhook():
    # ... (Verifikasi callback token tetap sama) ...
    data = request.get_json()
    external_id = data.get('external_id')
    status = data.get('status')

    invoice = Invoice.query.filter_by(external_id=external_id).first()
    if not invoice:
        return jsonify({"message": "Invoice tidak ditemukan"}), 404

    # Ambil reservasi yang terhubung
    reservation = Reservation.query.filter_by(invoice_id=invoice.id).first()

    if status == 'PAID':
        invoice.status = InvoiceStatus.PAID
        if reservation:
            reservation.payment_status = PaymentStatus.PAID
            
            # [LOGIKA BARU] Buat tiket setelah pembayaran lunas
            event = reservation.event_table.event
            new_ticket = Ticket(
                ticket_code=f"TIX-{uuid.uuid4().hex[:10].upper()}",
                user_id=reservation.user_id,
                invoice_id=invoice.id,
                event_id=event.id,
                expires_at=datetime.combine(event.event_date, event.end_time)
            )
            db.session.add(new_ticket)
            print(f"Tiket {new_ticket.ticket_code} dibuat untuk invoice {invoice.id}")

    elif status == 'EXPIRED':
        invoice.status = InvoiceStatus.EXPIRED
        if reservation:
            reservation.payment_status = PaymentStatus.EXPIRED
            event_table = EventTable.query.get(reservation.event_table_id)
            if event_table:
                event_table.status = EventTableStatus.AVAILABLE
                # Kembalikan stok produk
                for item in reservation.order_items:
                    item.product.stock += item.quantity
    
    db.session.commit()
    return jsonify({"status": "ok"}), 200

@reservation_bp.route("/my-tickets", methods=["GET"])
@jwt_required()
def get_my_tickets():
    """Endpoint untuk user melihat daftar tiket aktif miliknya."""
    current_user_id = get_jwt_identity()
    
    # Ambil tiket yang invoice-nya sudah lunas dan event-nya belum berakhir
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
            # Anda juga bisa menambahkan detail reservasi jika perlu
        } for t in active_tickets
    ])