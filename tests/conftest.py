import pytest
from app import app as flask_app, db
from bson import ObjectId

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",  # base en memoria     
        "WTF_CSRF_ENABLED": False
    })
    yield flask_app
    # Limpieza final
    db.client.drop_database("vehiculos_test")

@pytest.fixture
def client(app):
    return app.test_client()