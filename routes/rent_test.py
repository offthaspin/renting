from flask import Blueprint, jsonify

rent_test_bp = Blueprint("rent_test", __name__)

@rent_test_bp.route("/rent_test")
def rent_test():
    return jsonify({"status": "✅ rent_test route is working!"})
