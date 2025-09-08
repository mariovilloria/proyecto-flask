
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
import mongomock
from flask import Flask
from app import db   # ← importamos solo 'db', no 'app'




@pytest.fixture
def app():
    # 1. **NO TOCAMOS** el cliente real de Flask
    #    Creamos una app PARALEla que use mongomock
    mongo_client = mongomock.MongoClient()

    # 2. **Sustituimos la referencia global ANTES** de que Flask la use
    #    (esto reemplaza el MongoClient real que creas en app/__init__.py)
    #    **NO tocamos db.client (es solo lectura)**
    # **Sustituimos directamente el cliente y la base**
    db.client = mongo_client
    db.db = mongo_client["vehiculos_test"]

    # 3. **NO importamos 'app'** porque ya está inicializado
    #    Usamos la app que ya existe
    from app import app as flask_app
    # Configuramos la app que ya existe
    flask_app.config.update({
        "TESTING": True,
        "MONGO_URI": "mongomock://localhost/vehiculos_test",
        "WTF_CSRF_ENABLED": False
    })

    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()