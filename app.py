from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Invite, LicenseKey, init_db
from datetime import datetime, timedelta
import os
import secrets

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

init_db(app)


def is_setup_needed():
    return User.query.filter_by(is_admin=True).count() == 0


@app.before_request
def check_setup():
    if is_setup_needed() and request.endpoint not in ("setup", "static"):
        return redirect(url_for("setup"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if not is_setup_needed():
        return redirect(url_for("login"))

    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        password2 = request.form.get("password2", "").strip()

        if len(login_val) < 3:
            flash("Никнейм минимум 3 символа", "error")
            return render_template("setup.html")

        if len(password) < 4:
            flash("Пароль минимум 4 символа", "error")
            return render_template("setup.html")

        if password != password2:
            flash("Пароли не совпадают", "error")
            return render_template("setup.html")

        if User.query.filter_by(login=login_val).first():
            flash("Никнейм уже занят", "error")
            return render_template("setup.html")

        user = User(login=login_val, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Админ создан! Войдите", "success")
        return redirect(url_for("login"))

    return render_template("setup.html")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download")
def download():
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "liratine.tg.exe")
    has_file = os.path.exists(exe_path)
    return render_template("download.html", has_file=has_file)


@app.route("/download/file")
@login_required
def download_file():
    if not current_user.has_active_subscription():
        flash("Нужна активная подписка для скачивания", "error")
        return redirect(url_for("download"))
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "liratine.tg.exe")
    if os.path.exists(exe_path):
        return send_file(exe_path, as_attachment=True)
    flash("Файл не найден", "error")
    return redirect(url_for("download"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))

    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        invite_code = request.form.get("invite_code", "").strip().upper()

        if len(login_val) < 3:
            flash("Логин минимум 3 символа", "error")
            return render_template("register.html")

        if len(password) < 4:
            flash("Пароль минимум 4 символа", "error")
            return render_template("register.html")

        if len(invite_code) != 16:
            flash("Инвайт-код должен содержать 16 символов", "error")
            return render_template("register.html")

        invite = Invite.query.filter_by(code=invite_code).first()
        if not invite:
            flash("Неверный инвайт-код", "error")
            return render_template("register.html")

        if invite.used_by is not None:
            flash("Инвайт-код уже использован", "error")
            return render_template("register.html")

        if User.query.filter_by(login=login_val).first():
            flash("Логин уже занят", "error")
            return render_template("register.html")

        user = User(login=login_val)
        user.set_password(password)
        invite.used_by = user.id
        invite.used_at = datetime.utcnow()
        db.session.add(user)
        db.session.commit()

        flash("Аккаунт создан! Войдите", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))

    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(login=login_val).first()

        if user and user.check_password(password):
            if user.is_banned:
                flash("Аккаунт заблокирован", "error")
                return render_template("login.html")
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            return redirect(url_for("profile"))

        flash("Неверный логин или пароль", "error")

    return render_template("login.html")


@app.route("/profile")
@login_required
def profile():
    invites = Invite.query.filter_by(created_by=current_user.id).order_by(Invite.created_at.desc()).all()
    keys = LicenseKey.query.filter(
        (LicenseKey.created_by == current_user.id) | (LicenseKey.assigned_to == current_user.id)
    ).order_by(LicenseKey.created_at.desc()).all()
    return render_template("profile.html", user=current_user, invites=invites, keys=keys)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ===== LICENSE KEY ROUTES =====

@app.route("/profile/key/activate", methods=["POST"])
@login_required
def user_activate_key():
    key_code = request.form.get("key", "").strip().upper()
    if not key_code:
        flash("Введите ключ", "error")
        return redirect(url_for("profile"))

    lk = LicenseKey.query.filter_by(key=key_code).first()
    if not lk:
        flash("Неверный ключ", "error")
        return redirect(url_for("profile"))

    if lk.is_used:
        flash("Ключ уже использован", "error")
        return redirect(url_for("profile"))

    lk.is_used = True
    lk.assigned_to = current_user.id
    lk.used_at = datetime.utcnow()

    if current_user.subscription_expires and current_user.subscription_expires > datetime.utcnow():
        current_user.subscription_expires += timedelta(days=lk.days)
    else:
        current_user.subscription_expires = datetime.utcnow() + timedelta(days=lk.days)

    db.session.commit()
    flash(f"Ключ активирован! +{lk.days} дней подписки", "success")
    return redirect(url_for("profile"))


# ===== ADMIN =====

@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        flash("Нет доступа", "error")
        return redirect(url_for("profile"))
    users = User.query.all()
    total = len(users)
    banned = sum(1 for u in users if u.is_banned)
    hwid_banned = sum(1 for u in users if u.hwid_banned)
    expired = sum(1 for u in users if not u.is_admin and not u.has_active_subscription() and not u.is_banned)
    active = sum(1 for u in users if not u.is_banned and (u.is_admin or u.has_active_subscription()))
    invites = Invite.query.order_by(Invite.created_at.desc()).all()
    invites_used = sum(1 for i in invites if i.used_by is not None)
    keys = LicenseKey.query.order_by(LicenseKey.created_at.desc()).all()
    keys_used = sum(1 for k in keys if k.is_used)
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "liratine.tg.exe")
    has_file = os.path.exists(exe_path)
    return render_template(
        "admin.html",
        users=users,
        total=total,
        banned=banned,
        active=active,
        hwid_banned=hwid_banned,
        expired=expired,
        invites=invites,
        invites_used=invites_used,
        invites_free=len(invites) - invites_used,
        keys=keys,
        keys_used=keys_used,
        keys_free=len(keys) - keys_used,
        has_file=has_file,
    )


@app.route("/admin/ban/<int:user_id>", methods=["POST"])
@login_required
def admin_ban(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        user.is_banned = True
        db.session.commit()
        flash(f"{user.login} забанен", "success")
    return redirect(url_for("admin"))


@app.route("/admin/unban/<int:user_id>", methods=["POST"])
@login_required
def admin_unban(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user:
        user.is_banned = False
        db.session.commit()
        flash(f"{user.login} разбанен", "success")
    return redirect(url_for("admin"))


@app.route("/admin/delete/<int:user_id>", methods=["POST"])
@login_required
def admin_delete(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        flash("Пользователь удалён", "success")
    return redirect(url_for("admin"))


@app.route("/admin/setadmin/<int:user_id>", methods=["POST"])
@login_required
def admin_setadmin(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f"Админка {'выдана' if user.is_admin else 'снята'} для {user.login}", "success")
    return redirect(url_for("admin"))


@app.route("/admin/upload", methods=["POST"])
@login_required
def admin_upload():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    file = request.files.get("file")
    if file and file.filename:
        upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, "liratine.tg.exe"))
        flash("Файл загружен!", "success")
    else:
        flash("Файл не выбран", "error")
    return redirect(url_for("admin"))


@app.route("/admin/delete-file", methods=["POST"])
@login_required
def admin_delete_file():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "liratine.tg.exe")
    if os.path.exists(exe_path):
        os.remove(exe_path)
        flash("Файл удалён", "success")
    return redirect(url_for("admin"))


@app.route("/admin/invite/generate", methods=["POST"])
@login_required
def admin_generate_invite():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    count = int(request.form.get("count", 1))
    count = max(1, min(count, 50))
    for _ in range(count):
        invite = Invite(code=Invite.generate_code(), created_by=current_user.id)
        db.session.add(invite)
    db.session.commit()
    flash(f"Создано {count} инвайт-кодов", "success")
    return redirect(url_for("admin"))


@app.route("/admin/invite/delete/<int:invite_id>", methods=["POST"])
@login_required
def admin_delete_invite(invite_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    invite = db.session.get(Invite, invite_id)
    if invite and invite.used_by is None:
        db.session.delete(invite)
        db.session.commit()
        flash("Инвайт удалён", "success")
    return redirect(url_for("admin"))


@app.route("/profile/invite/generate", methods=["POST"])
@login_required
def user_generate_invite():
    invite = Invite(code=Invite.generate_code(), created_by=current_user.id)
    db.session.add(invite)
    db.session.commit()
    flash("Инвайт-код создан", "success")
    return redirect(url_for("profile"))


@app.route("/profile/invite/delete/<int:invite_id>", methods=["POST"])
@login_required
def user_delete_invite(invite_id):
    invite = db.session.get(Invite, invite_id)
    if invite and invite.created_by == current_user.id and invite.used_by is None:
        db.session.delete(invite)
        db.session.commit()
        flash("Инвайт удалён", "success")
    return redirect(url_for("profile"))


@app.route("/admin/subscription/<int:user_id>", methods=["POST"])
@login_required
def admin_set_subscription(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for("admin"))
    days = int(request.form.get("days", 0))
    days = max(0, min(days, 36500))
    if days > 0:
        if user.subscription_expires and user.subscription_expires > datetime.utcnow():
            user.subscription_expires += timedelta(days=days)
        else:
            user.subscription_expires = datetime.utcnow() + timedelta(days=days)
    else:
        user.subscription_expires = None
    db.session.commit()
    if days > 0:
        flash(f"Подписка {user.login}: +{days} дней (до {user.subscription_expires.strftime('%d.%m.%Y')})", "success")
    else:
        flash(f"Подписка {user.login} сброшена", "success")
    return redirect(url_for("admin"))


@app.route("/admin/hwid_ban/<int:user_id>", methods=["POST"])
@login_required
def admin_hwid_ban(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user:
        user.hwid_banned = True
        db.session.commit()
        flash(f"HWID {user.login} забанен", "success")
    return redirect(url_for("admin"))


@app.route("/admin/hwid_unban/<int:user_id>", methods=["POST"])
@login_required
def admin_hwid_unban(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user:
        user.hwid_banned = False
        db.session.commit()
        flash(f"HWID {user.login} разбанен", "success")
    return redirect(url_for("admin"))


# ===== LICENSE KEY ADMIN ROUTES =====

@app.route("/admin/key/generate", methods=["POST"])
@login_required
def admin_generate_key():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    count = int(request.form.get("count", 1))
    count = max(1, min(count, 50))
    days = int(request.form.get("days", 30))
    days = max(1, min(days, 36500))
    for _ in range(count):
        lk = LicenseKey(key=LicenseKey.generate_key(), days=days, created_by=current_user.id)
        db.session.add(lk)
    db.session.commit()
    flash(f"Создано {count} ключей ({days} дн.)", "success")
    return redirect(url_for("admin"))


@app.route("/admin/key/delete/<int:key_id>", methods=["POST"])
@login_required
def admin_delete_key(key_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    lk = db.session.get(LicenseKey, key_id)
    if lk and not lk.is_used:
        db.session.delete(lk)
        db.session.commit()
        flash("Ключ удалён", "success")
    return redirect(url_for("admin"))


# ===== API =====

@app.route("/api/auth", methods=["POST"])
def api_auth():
    data = request.get_json(silent=True) or {}
    login_val = data.get("login", "").strip()
    password = data.get("password", "").strip()
    hwid = data.get("hwid", "").strip()

    if not login_val or not password:
        return jsonify({"success": False, "message": "Missing login or password"}), 400

    user = User.query.filter_by(login=login_val).first()

    if not user or not user.check_password(password):
        return jsonify({"success": False, "message": "Invalid credentials"})

    if user.is_banned:
        return jsonify({"success": False, "message": "Account banned"})

    if user.hwid_banned:
        return jsonify({"success": False, "message": "Hardware banned"})

    if hwid:
        if user.hwid and user.hwid != hwid:
            return jsonify({"success": False, "message": "HWID mismatch — account bound to different hardware"})
        user.hwid = hwid

    if not user.has_active_subscription():
        return jsonify({"success": False, "message": "Subscription expired"})

    token = secrets.token_hex(32)
    user.session_token = token
    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "OK",
        "user_id": user.id,
        "username": user.login,
        "token": token,
        "subscription_expires": user.subscription_expires.strftime("%d.%m.%Y") if user.subscription_expires else None,
        "days_left": user.subscription_days_left(),
    })


@app.route("/api/verify", methods=["POST"])
def api_verify():
    data = request.get_json(silent=True) or {}
    login_val = data.get("login", "").strip()
    token = data.get("token", "").strip()
    hwid = data.get("hwid", "").strip()

    if not login_val or not token:
        return jsonify({"success": False, "message": "Missing login or token"}), 400

    user = User.query.filter_by(login=login_val).first()

    if not user or user.session_token != token:
        return jsonify({"success": False, "message": "Invalid token"})

    if user.is_banned:
        return jsonify({"success": False, "message": "Account banned"})

    if user.hwid_banned:
        return jsonify({"success": False, "message": "Hardware banned"})

    if hwid and user.hwid and user.hwid != hwid:
        return jsonify({"success": False, "message": "HWID mismatch"})

    if not user.has_active_subscription():
        return jsonify({"success": False, "message": "Subscription expired"})

    return jsonify({
        "success": True,
        "subscription_expires": user.subscription_expires.strftime("%d.%m.%Y") if user.subscription_expires else None,
        "days_left": user.subscription_days_left(),
    })


@app.route("/api/activate", methods=["POST"])
def api_activate_key():
    data = request.get_json(silent=True) or {}
    login_val = data.get("login", "").strip()
    password = data.get("password", "").strip()
    key_code = data.get("key", "").strip().upper()

    if not login_val or not password or not key_code:
        return jsonify({"success": False, "message": "Missing login, password, or key"}), 400

    user = User.query.filter_by(login=login_val).first()
    if not user or not user.check_password(password):
        return jsonify({"success": False, "message": "Invalid credentials"})

    if user.is_banned:
        return jsonify({"success": False, "message": "Account banned"})

    lk = LicenseKey.query.filter_by(key=key_code).first()
    if not lk:
        return jsonify({"success": False, "message": "Invalid key"})
    if lk.is_used:
        return jsonify({"success": False, "message": "Key already used"})

    lk.is_used = True
    lk.assigned_to = user.id
    lk.used_at = datetime.utcnow()

    if user.subscription_expires and user.subscription_expires > datetime.utcnow():
        user.subscription_expires += timedelta(days=lk.days)
    else:
        user.subscription_expires = datetime.utcnow() + timedelta(days=lk.days)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Key activated: +{lk.days} days",
        "subscription_expires": user.subscription_expires.strftime("%d.%m.%Y"),
        "days_left": user.subscription_days_left(),
    })


@app.route("/api/status")
def api_status():
    return jsonify({"status": "online"})


if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    app.run(host="0.0.0.0", port=80, debug=False)
