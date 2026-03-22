from dotenv import load_dotenv
load_dotenv()

from flask import Flask, make_response, redirect, url_for
from config import Config
from extensions import db
from flask_jwt_extended import JWTManager
import models
from flask_migrate import Migrate


def create_app():
    
    app = Flask(__name__)
    app.config.from_object(Config)


    db.init_app(app)
    Migrate(app, db) 

    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        return redirect(url_for("auth.login"))

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return redirect(url_for("auth.login"))

    @app.before_request
    def check_user_exists():
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        from flask import request
        from models.user import User
        # skip static files and auth routes
        if request.endpoint and (
            request.endpoint.startswith("auth.") or
            request.endpoint == "static" or
            request.endpoint.startswith("public") or
            request.endpoint == "mom.mom_client_sign"
        ):
            return
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
            if uid and User.query.get(uid) is None:
                resp = make_response(redirect(url_for("auth.login")))
                resp.delete_cookie("access_token_cookie")
                return resp
        except Exception:
            pass

    # register routes
    from routes.document_routes import document_bp
    from routes.auth_routes import auth_bp
    from routes.timeline_routes import timeline_bp
    from routes.compliance_routes import compliance_bp
    from routes.owner_routes import owner_bp
    from routes.approval_routes import approval_bp
    from routes.mom_routes import mom_bp
    from routes.reference_routes import ref_bp

    app.register_blueprint(document_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(approval_bp)
    app.register_blueprint(mom_bp)
    app.register_blueprint(ref_bp)

    @app.context_processor
    def inject_user_role():
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        from models.user import User
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
            if uid:
                user = User.query.get(uid)
                return {'current_user_role': user.role if user else ''}
        except Exception:
            pass
        return {'current_user_role': ''}

    with app.app_context():
        from models.compliance_models import ComplianceRequirement
        from models.mom import MeetingMinutes, MomItem
        from models.reference_board import ReferencePin
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)

