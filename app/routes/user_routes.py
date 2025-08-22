from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from datetime import datetime
import uuid
from xendit import Xendit, XenditError
from ..models import User, Invoice, Event, Ticket, Table
from .. import db
from ..utils import require_api_key

# Membuat Blueprint baru untuk user
user_bp = Blueprint('user', __name__)

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

@user_bp.route("/create-invoice", methods=["POST"])
@require_api_key
@jwt_required()
def handle_create_invoice():
    """Membuat invoice Xendit dan menyimpannya ke database."""
    data = request.get_json()
    amount_from_request = data.get('amount')
    user_id = data.get('user_id')
    event_id = data.get('event_id')

    if not all([amount_from_request, user_id, event_id]):
        return jsonify({"error": "Jumlah (amount), user_id, dan event_id diperlukan"}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User tidak ditemukan"}), 404
    
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event tidak ditemukan"}), 404

    correct_price = event.price
    if amount_from_request < correct_price:
        return jsonify({
            "error": "Jumlah pembayaran tidak sesuai.",
            "harga_seharusnya": correct_price,
            "harga_dikirim": amount_from_request
        }), 400

    invoice_object, error = create_xendit_invoice(
        correct_price,
        data.get('description', f'Tiket untuk {event.name} oleh {user.name}'), 
        user.email
    )
    
    if error:
        return jsonify({"error": "Gagal membuat invoice", "details": error}), 500
    
    new_invoice = Invoice(
        external_id=invoice_object.external_id,
        user_id=user.id,
        event_id=event.id, 
        amount=correct_price,
        status=invoice_object.status,
        invoice_url=invoice_object.invoice_url
    )
    db.session.add(new_invoice)
    db.session.commit()
    
    return jsonify({
        "message": "Invoice berhasil dibuat dan dicatat!",
        "invoice_url": invoice_object.invoice_url
    })

@user_bp.route("/create-virtual-account", methods=["POST"])
@require_api_key
@jwt_required()
def handle_create_va():
    """Membuat Virtual Account secara spesifik dan mengembalikan nomornya."""
    data = request.get_json()
    user_id = data.get('user_id')
    event_id = data.get('event_id')
    bank_code = data.get('bank_code')

    if not all([user_id, event_id, bank_code]):
        return jsonify({"error": "user_id, event_id, dan bank_code diperlukan"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User tidak ditemukan"}), 404
        
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event tidak ditemukan"}), 404

    correct_price = event.price

    existing_invoice = Invoice.query.filter_by(user_id=user.id, event_id=event.id, status='PENDING').first()
    if existing_invoice:
        return jsonify({"error": "Anda sudah memiliki transaksi pending untuk event ini."}), 409

    try:
        xendit_instance = Xendit(api_key=current_app.config['XENDIT_API_KEY'])
        external_id = f"va-flask-{uuid.uuid4()}"
        
        created_va = xendit_instance.VirtualAccount.create(
            external_id=external_id,
            bank_code=bank_code,
            name=user.name,
            expected_amount=correct_price,
            is_closed=True,
        )

        new_invoice = Invoice(
            external_id=external_id,
            user_id=user.id,
            event_id=event.id,
            amount=correct_price,
            status='PENDING',
            invoice_url=None
        )
        db.session.add(new_invoice)
        db.session.commit()
        
        return jsonify({
            "message": "Virtual Account berhasil dibuat.",
            "payment_details": {
                "external_id": created_va.external_id,
                "bank_code": created_va.bank_code,
                "account_number": created_va.account_number,
                "expected_amount": created_va.expected_amount,
                "name": created_va.name,
                "expiration_date": created_va.expiration_date
            }
        })
    except XenditError as e:
        return jsonify({"error": f"Error dari Xendit: {e.error_code}"}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Terjadi kesalahan: {e}"}), 500
    
@user_bp.route("/my-tickets", methods=["GET"])
@require_api_key
@jwt_required()
def get_my_tickets():
    """Endpoint untuk user di Flutter meminta daftar tiket aktif mereka."""
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
    tables = Table.query.all()
    return jsonify([
        {"id": t.id, "name": t.name, "type": t.type, "capacity": t.capacity}
        for t in tables
    ])

# List semua event yang aktif
@user_bp.route("/events", methods=["GET"])
@require_api_key
@jwt_required()
def user_get_events():
    events = Event.query.filter_by(is_active=True).all()
    return jsonify([
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "event_date": e.event_date.isoformat(),
            "start_time": str(e.start_time),
            "end_time": str(e.end_time),
            "price": e.price
        }
        for e in events
    ])

# Detail 1 event (beserta table yang tersedia)
@user_bp.route("/events/<int:event_id>", methods=["GET"])
@require_api_key
@jwt_required()
def user_get_event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return jsonify({
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "event_date": event.event_date.isoformat(),
        "start_time": str(event.start_time),
        "end_time": str(event.end_time),
        "price": event.price,
        "tables": [
            {
                "table_id": et.table_id,
                "status": et.status.value,
                "price": et.price
            }
            for et in event.event_tables
        ]
    })