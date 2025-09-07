import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'clave-local-fuerte')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DBNAME = os.getenv('MONGO_DBNAME', 'vehiculos_db')
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 1800