import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from .config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    try:
        db.init_app(app)
        migrate.init_app(app, db)
    except Exception as e:
        logging.error("Error initializing extensions: %s", e)
        raise

    # Register blueprints
    try:
        from .routes import bp as routes_bp
        app.register_blueprint(routes_bp)

    except ImportError as e:
        logging.error("Error importing blueprints: %s", e)
        raise
    except Exception as e:
        logging.error("Error registering blueprints: %s", e)
        raise

    return app
