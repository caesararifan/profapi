import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Memuat konfigurasi aplikasi dari environment variables."""
    APP_API_KEY = os.getenv('APP_API_KEY')
    XENDIT_API_KEY = os.getenv('XENDIT_SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "my-jwt-secret")
    XENDIT_CALLBACK_TOKEN = os.getenv('XENDIT_WEBHOOK_VERIFICATION_TOKEN')
    ADMIN_REGISTRATION_CODE = os.getenv('ADMIN_REGISTRATION_CODE')

    DB_USER = os.getenv('DB_USER')
    DB_PASS = os.getenv('DB_PASS')
    DB_HOST = os.getenv('DB_HOST')
    DB_NAME = os.getenv('DB_NAME')

    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'false').lower() in ['true', '1', 't'] 
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME') 
    ADMIN_WHATSAPP_NUMBER = os.getenv("ADMIN_WHATSAPP")
    
    SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BASE_STATIC = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static')

    UPLOAD_FOLDERS = {
       "products": os.path.join(BASE_STATIC, "product_images"),
       "events": os.path.join(BASE_STATIC, "event_images"),
       "banners": os.path.join(BASE_STATIC, "qrcodes")
    }
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}