import os

class Config:
    SQLALCHEMY_DATABASE_URI = (
        "mysql+mysqlconnector://landlord_user:admin3"
        "@localhost/landlord_app"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
