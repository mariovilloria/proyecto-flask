from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from app import mongo, User
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re
from app import db 
from bson import ObjectId
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if not current_user.password_changed:
            return redirect(url_for('auth.cambiar_clave'))
        return redirect(url_for('dashboard.administrador_dashboard'))
        
    if request.method == 'POST':
        cedula = request.form.get('cedula')
        password = request.form.get('password')
        
        if not cedula or not password:
            flash("Ambos campos son requeridos", "warning")
            return redirect(url_for('auth.login'))
            
        # Buscar usuario por cédula
        user = db.users.find_one({'cedula': cedula})
        if user and user.get('is_active', False):
            # Verificar si la contraseña es correcta
            if check_password_hash(user['password'], password):
                # Validar si es el primer login (password_changed=False)
                if not user.get('password_changed', True):  # Si es False
                    login_user(User(str(user['_id']), user['role'], user.get('name', 'Usuario')))
                    return redirect(url_for('auth.cambiar_clave'))
                else:
                    # Login normal
                    login_user(User(str(user['_id']), user['role'], user.get('name', 'Usuario')))
                    print(f"dashboard.{user['role']}_dashboard")
                    return redirect(url_for(f"dashboard.{user['role']}_dashboard"))
            else:
                flash("Contraseña incorrecta", "danger")
        else:
            flash("Credenciales inválidas o Usuario Inactivo", "danger")
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/cambiar_clave', methods=['GET', 'POST'])  # <-- Nombre más claro
@login_required
def cambiar_clave():
    # Obtener datos del usuario actual
    user = db.users.find_one({'_id': ObjectId(current_user.id)})
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')  # <-- Nuevo campo
        
        # Validar contraseña actual
        if not check_password_hash(user['password'], current_password):
            flash("Contraseña actual incorrecta", "danger")
            return redirect(url_for('auth.cambiar_clave'))
        
        # Validar que las nuevas contraseñas coincidan
        if new_password != confirm_password:
            flash("Las contraseñas no coinciden", "danger")
            return redirect(url_for('auth.cambiar_clave'))
        
        # Validar que la nueva contraseña no esté vacía
        if not new_password:
            flash("La nueva contraseña es requerida", "warning")
            return redirect(url_for('auth.cambiar_clave'))
        
        # Actualizar contraseña
        db.users.update_one(
            {'_id': user['_id']},
            {'$set': {'password': generate_password_hash(new_password), 'password_changed': True }}
        )
        
        flash("Contraseña actualizada correctamente", "success")
    
# Redirigir según el rol del usuario eliminado
        if user['role'] == 'cliente':
            return redirect(url_for('dashboard.cliente_dashboard'))
        elif user['role'] == 'tecnico':
            return redirect(url_for('dashboard.tecnico_dashboard'))
        elif user['role'] == 'supervisor':
            return redirect(url_for('dashboard.supervisor_dashboard'))
        else:  # administrador u otros roles
            return redirect(url_for('dashboard.administrador_dashboard'))    
    
    return render_template('auth/cambiar_clave.html', user=user)

def validate_password(password):
    """Valida que la contraseña tenga al menos 8 caracteres con letras y números"""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True