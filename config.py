import os
import secrets

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
DB_PATH = "database.db"
API_PORT = 80
