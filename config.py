import os
import secrets

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
DB_PATH = "database.db"
ADMIN_LOGIN = "sh4rpy"
ADMIN_PASSWORD = "cascascas1Z"
API_PORT = 80
