import pytest
from app import app as flask_app
import mongomock  # ← nueva librería

@pytest.fixture
def app():
    # Crear cliente FALSO en memoria
    mongo_client = mongomock.MongoClient()
    # Reemplazar el cliente real por el falso
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })
    # Sustituir la base de datos
    flask_app.config["MONGO_CLIENT"] = mongo_client
    # Actualizar la referencia global
    from app import db
    db.client = mongo_client
    db.name = "vehiculos_test"
    db.db = mongo_client["vehiculos_test"]

    yield flask_app

    # No hace falta drop_database: es memoria

@pytest.fixture
def client(app):
    return app.test_client()