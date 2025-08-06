# /my-api-project/app/models.py

from . import db  # Mengimpor instance db dari __init__.py
import uuid

class User(db.Model):
    __tablename__ = 'users' # Nama tabel di database
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    pin = db.Column(db.String(6), nullable=False)

    def __repr__(self):
        return f"<User {self.email}>"
    
class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = db.Column(db.String(255), unique=True, nullable=False) # ID dari Xendit
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False) # Menghubungkan ke tabel user
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='PENDING') # Status pembayaran
    invoice_url = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Invoice {self.id} - {self.status}>"