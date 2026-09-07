from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets
import string

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    hwid = db.Column(db.String(256))
    is_banned = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    subscription_expires = db.Column(db.DateTime)
    hwid_banned = db.Column(db.Boolean, default=False)
    hwid_ban_reason = db.Column(db.String(256))
    session_token = db.Column(db.String(64))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_active_subscription(self):
        if self.is_admin:
            return True
        if self.subscription_expires is None:
            return False
        return datetime.utcnow() <= self.subscription_expires

    def subscription_days_left(self):
        if self.is_admin:
            return 9999
        if self.subscription_expires is None:
            return 0
        delta = self.subscription_expires - datetime.utcnow()
        return max(0, delta.days)


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def generate_code():
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(16))
            if not Invite.query.filter_by(code=code).first():
                return code


class LicenseKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(32), unique=True, nullable=False)
    days = db.Column(db.Integer, default=30)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def generate_key():
        alphabet = string.ascii_uppercase + string.digits
        while True:
            key = "LIR-" + "-".join(
                "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)
            )
            if not LicenseKey.query.filter_by(key=key).first():
                return key


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _migrate_columns()


def _migrate_columns():
    with db.engine.connect() as engine:
        inspector = db.inspect(engine)
        tables = inspector.get_table_names()
        if "user" not in tables:
            return
        columns = [c["name"] for c in inspector.get_columns("user")]

        new_cols = {
            "subscription_expires": "ALTER TABLE user ADD COLUMN subscription_expires DATETIME",
            "hwid_banned": "ALTER TABLE user ADD COLUMN hwid_banned BOOLEAN DEFAULT 0",
            "hwid_ban_reason": "ALTER TABLE user ADD COLUMN hwid_ban_reason VARCHAR(256)",
            "session_token": "ALTER TABLE user ADD COLUMN session_token VARCHAR(64)",
        }
        for col_name, sql in new_cols.items():
            if col_name not in columns:
                engine.execute(db.text(sql))
