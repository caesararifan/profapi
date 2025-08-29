from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.models import Product

product_bp = Blueprint('product', __name__, url_prefix='/products')

@product_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_products_user():
    """Endpoint untuk user melihat daftar produk yang tersedia."""
    
    # Filter untuk produk yang stoknya masih ada
    products = Product.query.filter(Product.stock > 0).order_by(Product.name.asc()).all()
    
    products_list = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "image_url": p.image_url  # <-- GAMBAR DITAMBAHKAN DI SINI
        }
        for p in products
    ]
    
    return jsonify(products_list)