from flask import Flask
from config import Config
from extensions import db


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # register routes
    from routes.document_routes import document_bp
    app.register_blueprint(document_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)