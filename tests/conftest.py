# tests/conftest.py
import pytest
import mongomock
from app import create_app

@pytest.fixture
def app(monkeypatch):
    # 1. Cliente Mongo falso
    mongo_client = mongomock.MongoClient()

    # 2. Base de datos simulada (usa el mismo nombre que en tu app real)
    fake_db = mongo_client["test_db"]

    # 3. Parchar la referencia global db en tu app
    import app
    monkeypatch.setattr(app, "db", fake_db)

    # 4. Crear instancia de Flask en modo test
    app_instance = create_app({"TESTING": True})
    return app_instance


@pytest.fixture
def client(app):
    """Cliente de prueba de Flask"""
    return app.test_client()
