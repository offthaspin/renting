# init_db.py
from app import db, app, User
from datetime import datetime
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create all tables
    

    # Create admin user
    admin = User(
        full_name="Admin User",
        email="admin@example.com",
        login_phone="0712345678",
        password_hash=generate_password_hash("admin123"),  # hashed password
        is_admin=True,
        created_at=datetime.utcnow()
    )

    db.session.add(admin)
    db.session.commit()

    print("Database created and admin user added!")
