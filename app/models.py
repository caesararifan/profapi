from . import db
import uuid
from datetime import datetime
import enum
from sqlalchemy import UniqueConstraint

class EventTableStatus(enum.Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    UNAVAILABLE = "unavailable"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"

class InvoiceStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_id = db.Column(db.Integer, nullable=False, default=2)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nomor_hp = db.Column(db.String(14), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<User {self.email}>"

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Event {self.name}>"

class Table(db.Model):
    __tablename__ = 'tables'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return f"<Table {self.name} ({self.type})>"

class EventTable(db.Model):
    __tablename__ = 'event_tables'
    __table_args__ = (
        UniqueConstraint('event_id', 'table_id', name='_event_table_uc'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False)
    status = db.Column(db.Enum(EventTableStatus), default=EventTableStatus.AVAILABLE, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relasi
    event = db.relationship('Event', backref=db.backref('event_tables', lazy='dynamic'))
    table = db.relationship('Table', backref=db.backref('event_tables', lazy='dynamic'))

    def __repr__(self):
        return f"<EventTable EventID={self.event_id}, TableID={self.table_id}, Status={self.status}>"

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Integer, nullable=False) # Harga produk (dalam integer)
    stock = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<Product {self.name} - {self.price}>"

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = db.Column(db.String(255), unique=True, nullable=False) # ID dari payment gateway
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(InvoiceStatus), default=InvoiceStatus.PENDING, nullable=False)
    invoice_url = db.Column(db.String(255), nullable=True)
    
    user = db.relationship('User', backref=db.backref('invoices', lazy='dynamic'))

    def __repr__(self):
        return f"<Invoice {self.id} - {self.status}>"

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False) # TIPE DATA DIPERBAIKI
    event_table_id = db.Column(db.Integer, db.ForeignKey('event_tables.id'), nullable=False)
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoices.id'), nullable=True, unique=True) # Menyatukan pembayaran
    number_of_guests = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Integer, nullable=False) # Total harga (dalam integer)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('reservations', lazy='dynamic'))
    event_table = db.relationship('EventTable', backref=db.backref('reservations', lazy='dynamic'))
    invoice = db.relationship('Invoice', backref=db.backref('reservation', uselist=False, lazy='joined'))

    def __repr__(self):
        return f"<Reservation User={self.user_id}, EventTable={self.event_table_id}, Status={self.payment_status}>"

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Integer, nullable=False) # Subtotal (dalam integer)

    # Relationships
    reservation = db.relationship('Reservation', backref=db.backref('order_items', lazy='dynamic'))
    product = db.relationship('Product', backref=db.backref('order_items', lazy='dynamic'))

    def __repr__(self):
        return f"<OrderItem Reservation={self.reservation_id}, Product={self.product_id}, Qty={self.quantity}>"

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    ticket_code = db.Column(db.String(32), unique=True, nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoices.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('tickets', lazy='dynamic'))
    invoice = db.relationship('Invoice', backref=db.backref('tickets', lazy='dynamic')) # Relasi One-to-Many
    event = db.relationship('Event', backref=db.backref('tickets', lazy='dynamic'))

    def __repr__(self):
        return f'<Ticket {self.ticket_code}>'