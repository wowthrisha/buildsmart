import os

from flask import Blueprint, redirect, url_for, flash, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User

owner_bp = Blueprint("owner", __name__, url_prefix="/owner")


@owner_bp.route("/")
@jwt_required()
def owner_home():
    user = User.query.get(get_jwt_identity())
    if user.role != "Owner":
        flash("This section is for professional users.")
        return redirect(url_for("document.dashboard"))
    buildiq_url = os.getenv("BUILDIQ_URL", "http://localhost:8000")
    return render_template("owner_home.html", user=user, buildiq_url=buildiq_url)
