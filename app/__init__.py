from flask import Flask
from app.config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
mail = Mail()
jwt = JWTManager()

def create_app(config_class=Config):
    """Membuat dan mengkonfigurasi instance aplikasi Flask."""
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)

    # --- PERUBAHAN DI SINI ---
    # Impor semua blueprint baru dari folder routes
    from .routes.auth_routes import auth_bp
    from .routes.admin_routes import admin_bp
    from .routes.user_routes import user_bp
    from .routes.reservations import reservation_bp
    from app.routes.product_routes import product_bp

    # Daftarkan semua blueprint ke aplikasi
    app.register_blueprint(product_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(reservation_bp, url_prefix='/reservations')
    # -------------------------
    return app