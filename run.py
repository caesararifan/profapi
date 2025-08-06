# /my-api-project/run.py

from app import create_app, db

# Membuat aplikasi menggunakan factory
app = create_app()

# Perintah untuk membuat semua tabel database jika belum ada
# Ini akan dijalankan setiap kali server dimulai
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Jalankan aplikasi. Untuk produksi, gunakan server WSGI seperti Gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True)