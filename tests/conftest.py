import pytest
import mongomock
from app import create_app

@pytest.fixture(scope="session")
def app():
    """
    Crea una app Flask para testing con una DB simulada (mongomock).
    """
    # Inicializa la app en modo testing
    app = create_app("testing")
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False  # Desactiva CSRF para que los tests de login funcionen
    })

    # Usar mongomock en lugar de Mongo real
    mock_client = mongomock.MongoClient()
    app.db = mock_client["test_db"]

    yield app

@pytest.fixture
def client(app):
    """
    Cliente de pruebas que simula requests HTTP.
    """
    return app.test_client()

@pytest.fixture
def db(app):
    """
    Acceso directo a la base de datos mockeada (para poblarla en tests).
    """
    return app.db
