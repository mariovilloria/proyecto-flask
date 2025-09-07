from flask import Flask, render_template, url_for, redirect, flash, jsonify
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from flask_wtf.csrf import CSRFProtect
from flask_assets import Environment, Bundle
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Inicializar la app
app = Flask(__name__)
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'simple'})   # 5 min por defecto
# Filtros para paginación sin perder filtros
@app.template_filter('dict_delete')
def dict_delete(d, key):
    d = d.copy()
    d.pop(key, None)
    return d

@app.template_filter('dict_merge')
def dict_merge(d, extra):
    d = d.copy()
    d.update(extra)
    return d
app.config.from_object('config.Config')

# Configurar seguridad
csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-muy-fuerte-para-produccion')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Sesión expira en 30 minutos

# Configurar login
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Configurar MongoDB
mongo = MongoClient(app.config['MONGO_URI'])
db = mongo[app.config['MONGO_DBNAME']]

# Configurar assets (CSS/JS)
#assets = Environment(app)


# Clase de usuario para Flask-Login
class User(UserMixin):
    def __init__(self, id, role, name):
        super().__init__()
        self.id = id
        self.role = role
        self.name = name
    # Agregar propiedad para password_changed
    @property
    def password_changed(self):
        # Obtener el usuario actual de la base de datos
        user_data = db.users.find_one({'_id': ObjectId(self.id)})
        if user_data:
            return user_data.get('password_changed', False)
        return False        

# Importar rutas
from app.routes import auth, dashboard, usuarios, vehiculos, ordenes


# Cargar usuario para login
@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': ObjectId(user_id)})
    if not user_data:
        return None
    return User(user_id, user_data.get('role', 'cliente'), user_data.get('name', 'Usuario'))

# Registrar blueprints
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

# Configurar assets
#css_bundle = Bundle(
   # 'src/css/*.css',
   # filters='cssmin',
   # output='dist/css/main.min.css'
#)
#js_bundle = Bundle(
   # 'src/js/*.js',
    #filters='jsmin',
   # output='dist/js/main.min.js'
#)
#assets.register('css_all', css_bundle)
#assets.register('js_all', js_bundle)

# Funciones auxiliares
def get_current_user_info():
    if current_user.is_authenticated:
        return {
            'id': current_user.id,
            'role': current_user.role,
            'name': current_user.name
        }
    return None

#app.jinja_env.globals.update(get_current_user_info=get_current_user_info)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=generate_csrf)

@app.context_processor
def inject_current_user_info():
    if current_user.is_authenticated:
        return {
            'current_user_info': {
                'id': current_user.id,
                'role': current_user.role,
                'name': current_user.name
            }
        }
    return {'current_user_info': None}

@app.route('/')
def home():
    # Verificar si la base de datos está vacía
    if db.users.count_documents({}) == 0:
        # BD vacía: redirigir a registro
        return redirect(url_for('usuarios.registro', rol='administrador'))
    
    # Redirigir a dashboard si está autenticado
    if current_user.is_authenticated:
        role = current_user.role
        return redirect(url_for(f"dashboard.{role}_dashboard"))
    
    # BD tiene usuarios pero no está autenticado: redirigir a login
    return redirect(url_for('auth.login'))