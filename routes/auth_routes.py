from flask import Blueprint, request, redirect, url_for, render_template, make_response, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, unset_jwt_cookies, get_jwt_identity, set_access_cookies
from models.user import User
from extensions import db
import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

VALID_ROLES = {"Architect", "Engineer", "Contractor", "Authority", "Owner"}
ROLE_LIST   = ["Architect", "Engineer", "Contractor", "Authority", "Owner"]


def _current_user():
    return User.query.get(get_jwt_identity())

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            access_token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(hours=12))
            if user.role == "Owner":
                resp = make_response(redirect(url_for("owner.owner_home")))
            else:
                resp = make_response(redirect(url_for("document.dashboard")))
            set_access_cookies(resp, access_token)
            flash("Logged in successfully.", "success")
            return resp
        else:
            flash("Invalid email or password.", "error")

    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if role not in VALID_ROLES:
            role = "Engineer"

        if User.query.filter_by(email=email).first():
            flash("Email address already exists", "error")
            return redirect(url_for("auth.register"))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("auth.login"))
        
    return render_template("register.html")

@auth_bp.route("/logout")
def logout():
    resp = make_response(redirect(url_for("auth.login")))
    unset_jwt_cookies(resp)
    resp.delete_cookie("access_token_cookie")
    flash("You have been logged out.", "success")
    return resp


@auth_bp.route("/users")
@jwt_required()
def user_management():
    current = _current_user()
    if current.role not in ['Authority', 'Architect']:
        return redirect(url_for('document.dashboard'))
    users = User.query.order_by(User.role, User.username).all()
    return render_template('user_management.html',
                           all_users=users,
                           roles=ROLE_LIST,
                           user=current)


@auth_bp.route("/users/<int:user_id>/set-role", methods=["POST"])
@jwt_required()
def set_user_role(user_id):
    current = _current_user()
    if current.role not in ['Authority', 'Architect']:
        return redirect(url_for('document.dashboard'))
    target = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role in VALID_ROLES:
        target.role = new_role
        db.session.commit()
        flash(f'Role updated to {new_role}.', 'success')
    return redirect(url_for('auth.user_management'))
