import os

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-random-string")
DB_PATH = "database.db"
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin"
API_PORT = 80
