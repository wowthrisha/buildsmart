from flask import Flask, redirect, url_for
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

    # register routes
    from routes.document_routes import document_bp
    from routes.auth_routes import auth_bp
    from routes.timeline_routes import timeline_bp
    from routes.compliance_routes import compliance_bp

    app.register_blueprint(document_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(compliance_bp)

    with app.app_context():
        from models.compliance_models import ComplianceRequirement
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)