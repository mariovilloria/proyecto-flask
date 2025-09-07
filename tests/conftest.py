import pytest
from app import app as flask_app
from app import db

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })
    yield flask_app
    # Limpieza solo si NO es mongomock
    if not flask_app.config["MONGO_URI"].startswith("mongomock"):
        db.client.drop_database("vehiculos_test")

@pytest.fixture
def client(app):
    return app.test_client()