from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.models import Product

product_bp = Blueprint('product', __name__, url_prefix='/products')

@product_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_products_user():
    """Endpoint untuk user melihat daftar produk yang tersedia."""
    # Anda bisa menambahkan filter, misalnya hanya produk dengan stok > 0
    products = Product.query.filter(Product.stock > 0).all()
    return jsonify([
        {"id": p.id, "name": p.name, "description": p.description, "price": p.price}
        for p in products
    ])