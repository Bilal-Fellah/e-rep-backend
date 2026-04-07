import pytest
import os

from api import create_app
from api import db as _db  # adjust to your db import


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
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    yield app


@pytest.fixture(scope="session")
def db(app):
    """Create all tables once per session, drop after."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope="function")
def db_session(db):
    """Wrap each test in a transaction that rolls back after."""
    connection = db.engine.connect()
    transaction = connection.begin()
    session = db.session

    yield session

    session.close()
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