from app import create_app, db
from app.models import User, Table, Product, Event, EventTable, Invoice, Ticket, OrderItem, Reservation
from werkzeug.security import generate_password_hash
from datetime import date, time, timedelta
import random

def seed_data():
    """
    Fungsi untuk mengisi database dengan data dummy yang banyak dan bervariasi.
    """
    
    print("Menghapus semua data lama...")
    # Urutan penghapusan harus benar untuk menghindari error foreign key
    OrderItem.query.delete()
    Ticket.query.delete()
    Reservation.query.delete()
    Invoice.query.delete()
    EventTable.query.delete()
    Product.query.delete()
    Table.query.delete()
    Event.query.delete()
    User.query.delete()
    db.session.commit()
    print("Data lama berhasil dihapus.")

    print("\nMembuat data baru...")
    try:
        # --- 1. Buat Users ---
        users_to_create = [
            User(name="Admin Utama", email="admin@example.com", password_hash=generate_password_hash("password123", method='pbkdf2:sha256'), role_id=1),
            User(name="Andi Budiman", email="andi.b@example.com", password_hash=generate_password_hash("password123", method='pbkdf2:sha256'), role_id=2),
            User(name="Citra Lestari", email="citra.l@example.com", password_hash=generate_password_hash("password123", method='pbkdf2:sha256'), role_id=2),
            User(name="Dewi Anggraini", email="dewi.a@example.com", password_hash=generate_password_hash("password123", method='pbkdf2:sha256'), role_id=2),
            User(name="Eko Prasetyo", email="eko.p@example.com", password_hash=generate_password_hash("password123", method='pbkdf2:sha256'), role_id=2),
        ]
        db.session.add_all(users_to_create)
        db.session.commit()
        print(f"{len(users_to_create)} Users dibuat.")

        # --- 2. Buat Tables ---
        tables_to_create = [
            # Sofa
            Table(name="Sofa VVIP 1 (Center)", type="Sofa", capacity=10, price=3500000),
            Table(name="Sofa VIP 2 (Left)", type="Sofa", capacity=8, price=2500000),
            Table(name="Sofa VIP 3 (Right)", type="Sofa", capacity=8, price=2500000),
            # Round Table
            Table(name="Round Table A1", type="Round", capacity=4, price=1200000),
            Table(name="Round Table A2", type="Round", capacity=4, price=1200000),
            Table(name="Round Table B1", type="Round", capacity=6, price=1800000),
            Table(name="Round Table B2", type="Round", capacity=6, price=1800000),
            # High Chair
            Table(name="High Chair C1", type="High Chair", capacity=2, price=800000),
            Table(name="High Chair C2", type="High Chair", capacity=2, price=800000),
            Table(name="High Chair D1", type="High Chair", capacity=3, price=1000000),
            # Standing
            Table(name="Standing Area", type="Standing", capacity=50, price=450000),
        ]
        db.session.add_all(tables_to_create)
        db.session.commit()
        print(f"{len(tables_to_create)} Tables dibuat.")

        # --- 3. Buat Products ---
        products_to_create = [
            # Minuman Alkohol
            Product(name="Chivas Regal 12", description="1 Botol 750ml", price=1500000, stock=30),
            Product(name="Johnnie Walker Black Label", description="1 Botol 750ml", price=1400000, stock=30),
            Product(name="Jack Daniel's Old No. 7", description="1 Botol 750ml", price=1300000, stock=40),
            Product(name="Heineken Tower", description="3 Liter", price=550000, stock=50),
            Product(name="Bintang Bucket", description="5 Botol", price=250000, stock=100),
            # Makanan
            Product(name="Wagyu Steak", description="200gr Wagyu MB5+ with sauce", price=350000, stock=50),
            Product(name="Truffle Pizza", description="8 slices with black truffle", price=180000, stock=80),
            Product(name="Calamari Rings", description="Crispy fried calamari with tartar", price=95000, stock=100),
            Product(name="French Fries", description="Classic shoestring fries", price=55000, stock=200),
            # Minuman Non-Alkohol
            Product(name="Mineral Water", description="Aqua Reflection 380ml", price=35000, stock=300),
            Product(name="Coca-cola", description="Can 330ml", price=40000, stock=200),
        ]
        db.session.add_all(products_to_create)
        db.session.commit()
        print(f"{len(products_to_create)} Products dibuat.")

        # --- 4. Buat Events ---
        today = date.today()
        events_to_create = [
            Event(name="Acoustic Night Special", description="Nikmati malam syahdu dengan musisi akustik terbaik.", event_date=today + timedelta(days=10), start_time=time(20, 0, 0), end_time=time(23, 0, 0), is_active=True),
            Event(name="EDM Festival Vol. 3", description="Pesta dansa elektronik dengan DJ internasional.", event_date=today + timedelta(days=30), start_time=time(21, 0, 0), end_time=time(3, 0, 0), is_active=True),
            Event(name="Ladies Night Out", description="Promo spesial untuk para wanita sepanjang malam.", event_date=today + timedelta(days=7), start_time=time(19, 0, 0), end_time=time(23, 59, 0), is_active=True),
            Event(name="Tribute to Queen (PAST EVENT)", description="Malam nostalgia dengan lagu-lagu legendaris Queen.", event_date=today - timedelta(days=20), start_time=time(20, 30, 0), end_time=time(23, 30, 0), is_active=False),
            Event(name="New Year Eve Party 2026", description="Sambut tahun baru dengan kemeriahan tak terlupakan.", event_date=date(2025, 12, 31), start_time=time(20, 0, 0), end_time=time(4, 0, 0), is_active=True),
        ]
        db.session.add_all(events_to_create)
        db.session.commit()
        print(f"{len(events_to_create)} Events dibuat.")

        # --- 5. Hubungkan Tables ke Events (EventTable) ---
        all_tables = Table.query.all()
        all_events = Event.query.filter_by(is_active=True).all()
        
        for event in all_events:
            # Pilih secara acak beberapa meja untuk setiap event
            num_tables_for_event = random.randint(5, len(all_tables))
            tables_for_this_event = random.sample(all_tables, num_tables_for_event)
            
            for table in tables_for_this_event:
                et = EventTable(event_id=event.id, table_id=table.id)
                db.session.add(et)
        
        db.session.commit()
        print("EventTables dibuat (meja dijadwalkan secara acak ke event aktif).")

        print("\nProses seeding data selesai! Database Anda siap untuk diuji.")

    except Exception as e:
        db.session.rollback()
        print(f"\nTerjadi error saat seeding data: {e}")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Baris yang menyebabkan error telah dihapus
        seed_data()