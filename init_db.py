# init_db.py
from app import app
from extensions import db
from models import User, Tenant, AuditLog  # import all your models
from datetime import datetime
from werkzeug.security import generate_password_hash

# Admin credentials
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin@1234"

with app.app_context():
    # 1️⃣ Drop all tables if you want a clean start (optional)
    # db.drop_all()

    # 2️⃣ Create tables in MySQL
    db.create_all()
    print("✅ Tables created successfully in MySQL")

    # 3️⃣ Create admin user if it doesn't exist
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            full_name="Admin User",
            email=ADMIN_EMAIL,
            login_phone="0712345678",
            password_hash=generate_password_hash(ADMIN_PASSWORD),
            is_admin=True,
            created_at=datetime.utcnow()
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created")
    else:
        print("ℹ️ Admin user already exists")
