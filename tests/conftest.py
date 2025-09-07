# tests/conftest.py
import pytest
import mongomock
from app import app as flask_app, db  # importar app y db reales
import app as app_module

@pytest.fixture
def app(monkeypatch):
    """Crea una app de Flask para tests con mongomock."""

    # Crear cliente de Mongo falso
    mongo_client = mongomock.MongoClient()
    test_db = mongo_client['test_database']

    # Reemplazar db de la app por la db de prueba
    monkeypatch.setattr(app_module, 'db', test_db)

    # Configuración de testing
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
# tests/conftest.py
import pytest
import mongomock
from app import app as flask_app
import app as app_module

@pytest.fixture
def app(monkeypatch):
    """Crea una app Flask para tests usando mongomock y desactiva CSRF."""

    # 1. Crear cliente de Mongo falso y DB de prueba
    mongo_client = mongomock.MongoClient()
    test_db = mongo_client['test_database']

    # 2. Reemplazar db de la app por la DB de prueba
    monkeypatch.setattr(app_module, 'db', test_db)

    # 3. Configurar testing y desactivar CSRF
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
