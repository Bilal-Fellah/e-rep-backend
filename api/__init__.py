from flask import Flask

def create_app():
    app = Flask(__name__)

    from .routes import callback_bp
    app.register_blueprint(callback_bp)

    return app
