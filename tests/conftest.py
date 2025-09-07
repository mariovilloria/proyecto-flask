import pytest
import mongomock
from app import app as flask_app
from pymongo import MongoClient

@pytest.fixture
def app():
    # 1. Crear cliente FALSO en memoria
    mongo_client = mongomock.MongoClient()

    # 2. **Sobrescribir la variable global ANTES** de que Flask la use
    #    (esto reemplaza el MongoClient real que creas en app/__init__.py)
    from app import db
    # IMPORTANTE: no tocamos db.client (es solo lectura)
    # Sustituimos directamente el cliente y la base
    db.client = mongo_client
    db.db = mongo_client["vehiculos_test"]

    # 3. Configurar Flask
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })

    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()