import pytest
import mongomock
from app import app as flask_app   # ← importas la variable 'app' que YA existe

@pytest.fixture
def app():
    # 1. **NO TOCAMOS** el cliente real de Flask
    #    Creamos una app PARALEla que use mongomock
    mongo_client = mongomock.MongoClient()

    # 2. **Sustituimos la referencia global ANTES** de que Flask la use
    #    (esto reemplaza el MongoClient real que creas en app/__init__.py)
    #    **NO tocamos db.client (es solo lectura)**
    from app import db
    # **Sustituimos directamente el cliente y la base**
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