import pytest
import mongomock
from app import app as flask_app
from app import db   # esto importa el cliente ACTUAL

@pytest.fixture
def app():
    # 1. Crear cliente FALSO
    mongo_client = mongomock.MongoClient()

    # 2. Reemplazar el cliente ANTES de que Flask arranque
    #    Como en tu __init__.py haces algo como:
    #    mongo = MongoClient(...)  → ahora lo sobreescribimos
    db.client = mongo_client
    db.db = mongo_client["vehiculos_test"]

    # 3. Configurar Flask
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })

    yield flask_app

    # 4. No hace falta drop_database: es memoria

@pytest.fixture
def client(app):
    return app.test_client()