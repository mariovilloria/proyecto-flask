import pytest
import mongomock
from app import app as flask_app

@pytest.fixture
def app():
    # 1. Cliente FALSO en memoria
    mongo_client = mongomock.MongoClient()

    # 2. Sustituir el cliente ANTES de que Flask arranque
    #    (esto sobrescribe el cliente real que creas en app/__init__.py)
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })
    # Reemplazamos la referencia global
    from app import db
    db.client = mongo_client
    db.db = mongo_client["vehiculos_test"]

    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()