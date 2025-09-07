import pytest
import mongomock
from flask import Flask
from app import app as flask_app

@pytest.fixture
def app():
    # 1. Crear cliente FALSO en memoria
    mongo_client = mongomock.MongoClient()

    # 2. **NO tocamos** el cliente real de Flask
    #    Creamos una app PARALEla que use mongomock
    from app import db
    # Sustituimos TODO el cliente y la base
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