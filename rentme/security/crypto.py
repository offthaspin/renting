import os
from cryptography.fernet import Fernet

_key = os.getenv("MASTER_ENCRYPTION_KEY")
if not _key:
    raise RuntimeError("MASTER_ENCRYPTION_KEY missing")

fernet = Fernet(_key.encode() if isinstance(_key, str) else _key)

def encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.encrypt(value.encode()).decode()

def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.decrypt(value.encode()).decode()
