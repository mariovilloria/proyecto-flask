import mongomock
import pytest
from app import app as flask_app
from app import extensions

@pytest.fixture
def app():
    # Crear cliente mongomock
    mongo_client = mongomock.MongoClient()
    # Sustituir el cliente y la base global
    extensions.mongo = mongo_client
    extensions.db = mongo_client["vehiculos_test"]

    # Configuración de la app de pruebas
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False,
    })
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()
