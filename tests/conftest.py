import pytest
from app import app as flask_app, db
from bson import ObjectId

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongodb://localhost:27017/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })
    yield flask_app
    # Limpieza final
    db.client.drop_database("vehiculos_test")

@pytest.fixture
def client(app):
    return app.test_client()