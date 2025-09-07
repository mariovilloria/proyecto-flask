# tests/conftest.py
import pytest
import mongomock
from app import create_app  # importa tu factory de Flask
import app

@pytest.fixture
def app(monkeypatch):
    """Crea una app de Flask para tests con base de datos mongomock."""
    
    # 1. Crear cliente de Mongo falso
    mongo_client = mongomock.MongoClient()
    test_db = mongo_client['test_database']  # nombre de la DB de prueba

    # 2. Reemplazar MongoClient en tu app antes de crearla
    # Suponiendo que en __init__.py haces: mongo = MongoClient(...).db_name
    monkeypatch.setattr('myapp.MongoClient', mongomock.MongoClient)

    # 3. Crear la app de Flask con configuración de TESTING
    app = create_app({'TESTING': True})

    # 4. Reemplazar db de tu app por el db de prueba
    # Esto depende de cómo estés usando db, ejemplo:
    # si en tu app haces: from myapp import db
    # entonces:
    monkeypatch.setattr(myapp, 'db', test_db)

    yield app

@pytest.fixture
def client(app):
    """Fixture para usar el test client de Flask."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Fixture para usar el test CLI runner de Flask."""
    return app.test_cli_runner()
