# /my-api-project/app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from .config import Config

# Inisialisasi ekstensi tanpa mengikatnya ke aplikasi dulu
db = SQLAlchemy()
bcrypt = Bcrypt()

def create_app(config_class=Config):
    """Membuat dan mengkonfigurasi instance aplikasi Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Mengikat ekstensi ke instance aplikasi
    db.init_app(app)
    bcrypt.init_app(app)

    # Mengimpor dan mendaftarkan blueprint dari routes
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app