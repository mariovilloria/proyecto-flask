import pytest
import mongomock
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app   # ← ahora Python encontrará app

@pytest.fixture
def app():
    mongo_client = mongomock.MongoClient()
    from app import db
    db.client = mongo_client
    db.db = mongo_client["vehiculos_test"]

    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()