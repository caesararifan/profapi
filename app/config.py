# /my-api-project/app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Memuat konfigurasi aplikasi dari environment variables."""
    # Kunci Keamanan
    APP_API_KEY = os.getenv('APP_API_KEY')
    XENDIT_API_KEY = os.getenv('XENDIT_SECRET_KEY')

    # Konfigurasi Database
    DB_USER = os.getenv('DB_USER')
    DB_PASS = os.getenv('DB_PASS')
    DB_HOST = os.getenv('DB_HOST')
    DB_NAME = os.getenv('DB_NAME')
    
    SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False