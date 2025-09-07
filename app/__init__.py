from flask import Flask, render_template, url_for, redirect, flash
from flask_login import LoginManager, UserMixin, current_user
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from pymongo import MongoClient
from datetime import timedelta
from bson import ObjectId
import os

def create_app(config_name=None):
    app = Flask(__name__)

    # Config
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-muy-fuerte-para-produccion')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
    if config_name == "testing":
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # desactivar CSRF en tests

    # Cache
    cache = Cache(app, config={'CACHE_TYPE': 'simple'})

    # CSRF
    csrf = CSRFProtect(app)

    # Login
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'

    # MongoDB
    if config_name == "testing":
        import mongomock
        app.db = mongomock.MongoClient()["test_db"]
    else:
        mongo = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
        app.db = mongo[os.environ.get("MONGO_DBNAME", "mydb")]

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.usuarios import usuarios_bp
    from app.routes.vehiculos import vehiculos_bp
    from app.routes.ordenes import ordenes_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
    app.register_blueprint(vehiculos_bp, url_prefix='/vehiculos')
    app.register_blueprint(ordenes_bp, url_prefix='/ordenes')

    # Usuario para login
    class User(UserMixin):
        def __init__(self, id, role, name):
            super().__init__()
            self.id = id
            self.role = role
            self.name = name

        @property
        def password_changed(self):
            user_data = app.db.users.find_one({'_id': ObjectId(self.id)})
            return user_data.get('password_changed', False) if user_data else False

    @login_manager.user_loader
    def load_user(user_id):
        user_data = app.db.users.find_one({'_id': ObjectId(user_id)})
        if not user_data:
            return None
        return User(user_id, user_data.get('role', 'cliente'), user_data.get('name', 'Usuario'))

    # Context processors
    @app.context_processor
    def inject_current_user_info():
        if current_user.is_authenticated:
            return {'current_user_info': {'id': current_user.id, 'role': current_user.role, 'name': current_user.name}}
        return {'current_user_info': None}

    # Routes
    @app.route('/')
    def home():
        if app.db.users.count_documents({}) == 0:
            return redirect(url_for('usuarios.registro', rol='administrador'))
        if current_user.is_authenticated:
            return redirect(url_for(f"dashboard.{current_user.role}_dashboard"))
        return redirect(url_for('auth.login'))

    return app
