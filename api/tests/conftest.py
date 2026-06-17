import api.tests.conftest_setup
import pytest
import os

from api import create_app
from api import db as _db  # adjust to your db import

# Ensure all models are imported so SQLAlchemy metadata is populated
import api.models.user_model
import api.models.category_model
import api.models.entity_model
import api.models.entity_category_model
import api.models.page_model
import api.models.page_history_model
import api.models.post_model
import api.models.note_model


@pytest.fixture(scope="session")
def app():
    """Create app with testing config."""
    defaults = {
        "VPS_ADDRESS": "localhost",
        "VPS_DB_PORT": "5432",
        "DB_USER": "test_user",
        "DB_PWD": "test_pwd",
        "DB_NAME": "test_db",
        "SECRET_KEY": "test-secret",
        "FRONTEND_REDIRECT_URL": "http://localhost:3000",
        "FRONTEND_COOKIE_DOMAIN": "localhost",
        "COOKIE_SECURE": "false",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    os.environ["TESTING"] = "true"

    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # Use in-memory SQLite for tests
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    })
    
    # Dispose old engine and create new one with SQLite config
    with app.app_context():
        _db.engine.dispose()
    
    yield app


@pytest.fixture(scope="session", autouse=True)
def db(app):
    """Create all tables once per session, drop after."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope="function")
def db_session(db, app):
    """Wrap each test in a transaction that rolls back after."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Use the session's connection with our transaction
        session = db.session
        session.begin_nested()

        yield session

        session.rollback()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(app):
    """Flask test client for API tests."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """CLI runner for testing Flask commands."""
    return app.test_cli_runner()