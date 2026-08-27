from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, init_db
from config import SECRET_KEY
from datetime import datetime
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "secre66ttk982eey2y3ys"
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
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "LirisenseLoader.exe")
    has_file = os.path.exists(exe_path)
    return render_template("download.html", has_file=has_file)


@app.route("/download/file")
@login_required
def download_file():
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "LirisenseLoader.exe")
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

        if len(login_val) < 3:
            flash("Логин минимум 3 символа", "error")
            return render_template("register.html")

        if len(password) < 4:
            flash("Пароль минимум 4 символа", "error")
            return render_template("register.html")

        if User.query.filter_by(login=login_val).first():
            flash("Логин уже занят", "error")
            return render_template("register.html")

        user = User(login=login_val)
        user.set_password(password)
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
    return render_template("profile.html", user=current_user)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        flash("Нет доступа", "error")
        return redirect(url_for("profile"))
    users = User.query.all()
    total = len(users)
    banned = sum(1 for u in users if u.is_banned)
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "LirisenseLoader.exe")
    has_file = os.path.exists(exe_path)
    return render_template("admin.html", users=users, total=total, banned=banned, active=total - banned, has_file=has_file)


@app.route("/admin/ban/<int:user_id>")
@login_required
def admin_ban(user_id):
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    user = db.session.get(User, user_id)
    if user:
        user.is_banned = True
        db.session.commit()
        flash(f"{user.login} забанен", "success")
    return redirect(url_for("admin"))


@app.route("/admin/unban/<int:user_id>")
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


@app.route("/admin/delete/<int:user_id>")
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


@app.route("/admin/setadmin/<int:user_id>")
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
        file.save(os.path.join(upload_dir, "LirisenseLoader.exe"))
        flash("Файл загружен!", "success")
    else:
        flash("Файл не выбран", "error")
    return redirect(url_for("admin"))


@app.route("/admin/delete-file")
@login_required
def admin_delete_file():
    if not current_user.is_admin:
        return redirect(url_for("profile"))
    exe_path = os.path.join(os.path.dirname(__file__), "uploads", "LirisenseLoader.exe")
    if os.path.exists(exe_path):
        os.remove(exe_path)
        flash("Файл удалён", "success")
    return redirect(url_for("admin"))


# ===== API =====

@app.route("/api/auth", methods=["GET", "POST"])
def api_auth():
    if request.method == "GET":
        login_val = request.args.get("login")
        password = request.args.get("password")
        hwid = request.args.get("hwid")
    else:
        data = request.get_json(silent=True) or {}
        login_val = data.get("login")
        password = data.get("password")
        hwid = data.get("hwid")

    if not login_val or not password:
        return jsonify({"success": False, "message": "Missing login or password"}), 400

    user = User.query.filter_by(login=login_val).first()

    if not user or not user.check_password(password):
        return jsonify({"success": False, "message": "Invalid credentials"})

    if user.is_banned:
        return jsonify({"success": False, "message": "Account banned"})

    if hwid:
        user.hwid = hwid
    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "message": "OK", "user_id": user.id})


@app.route("/api/status")
def api_status():
    return jsonify({"status": "online"})


if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    app.run(host="0.0.0.0", port=80, debug=False)
