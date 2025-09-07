# tests/conftest.py
import pytest
import mongomock
from app import app as flask_app
import app as app_module  # importa tu módulo para reemplazar db

@pytest.fixture
def app(monkeypatch):
    # Crear DB de prueba
    test_db = mongomock.MongoClient().my_database

    # Reemplazar la variable db de tu app por la de prueba
    monkeypatch.setattr(app_module, 'db', test_db)

    # Configuración de test
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False  # desactiva CSRF

    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()
