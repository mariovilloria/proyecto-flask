# tests/conftest.py
import pytest
import mongomock
import app as app_module

@pytest.fixture
def app(monkeypatch):
    # 1. Cliente Mongo falso
    mongo_client = mongomock.MongoClient()
    fake_db = mongo_client["test_db"]

    # 2. Parchar la referencia global db en tu módulo app
    monkeypatch.setattr(app_module, "db", fake_db)

    # 3. Activar modo testing en la instancia global de Flask
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False

    return app_module.app


@pytest.fixture
def client(app):
    """Cliente de prueba de Flask"""
    return app.test_client()
