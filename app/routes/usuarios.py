from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import current_user, login_required
from app import mongo
from datetime import datetime
from bson import ObjectId
from app import db
from werkzeug.security import generate_password_hash

usuarios_bp = Blueprint('usuarios', __name__)

#@usuarios_bp.route('/registro/', methods=['GET', 'POST'])
@usuarios_bp.route('/registro/<rol>', methods=['GET', 'POST'])
@login_required
def registro(rol=None):
    is_first_user = db.users.count_documents({}) == 0

    if request.method == 'POST':
        # ----------- DETECTAR SI ES EDICIÓN -----------
        editing = request.form.get('editing')
        user_id = request.form.get('user_id')

        name = request.form.get('name')
        cedula = request.form.get('cedula')
        phone = request.form.get('phone')
        address = request.form.get('address')
        email = request.form.get('email')

        # SI ES EDICIÓN --------------------------------
        if editing and user_id:
            data_update = {
                "name": name,
                "cedula": cedula,
                "phone": phone,
                "address": address,
                "email": email
            }
            # Si es técnico, actualizar especialidad
            if request.form.get('specialty') is not None:
                data_update['especialidad'] = request.form.get('specialty')

            db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': data_update}
            )

            flash("Usuario actualizado correctamente", "success")
            # Redirigimos según el rol
            if rol == 'tecnico':
                return redirect(url_for('usuarios.list_tecnicos'))
            elif rol == 'cliente':
                return redirect(url_for('usuarios.list_clientes'))
            elif rol == 'supervisor':
                return redirect(url_for('usuarios.list_supervisores'))
            elif rol == 'vendedor':
                return redirect(url_for('usuarios.list_vendedores'))
            else:
                return redirect(url_for('dashboard.administrador_dashboard'))

        # ---------------------------------------------
        # SI ES REGISTRO NUEVO
        role = 'administrador' if is_first_user else rol
        password = cedula

        required_fields = [name, cedula]
        if not is_first_user:
            required_fields.append(role)

        if not all(required_fields):
            flash("Nombre y cédula son requeridos", "warning")
            return redirect(url_for('usuarios.registro', rol=role))

        # verificar cédula duplicada SOLO para creación
        if db.users.find_one({'cedula': cedula}):
            flash("La cédula ya está en uso", "info")
            return redirect(url_for('usuarios.registro', rol=role))

        user_data = {
            'name': name,
            'cedula': cedula,
            'phone': phone,
            'address': address,
            'email': email,
            'role': role,
            'password': generate_password_hash(password, method='pbkdf2:sha256', salt_length=16),
            'is_active': True,
            'password_changed': False,
            'created_at': datetime.now()
        }

        # Specialidad si es técnico
        if role == 'tecnico':
            specialty = request.form.get('specialty', '')
            user_data['especialidad'] = specialty

        db.users.insert_one(user_data)
        flash("Usuario registrado correctamente", "success")

        # Redirección nueva
        if is_first_user:
            return redirect(url_for('auth.login'))
        else:
            if role == 'administrador':
                return redirect(url_for('dashboard.administrador_dashboard'))
            elif role == 'supervisor':
                return redirect(url_for('usuarios.list_supervisores'))
            elif role == 'tecnico':
                return redirect(url_for('usuarios.list_tecnicos'))
            elif role == 'cliente':
                return redirect(url_for('usuarios.list_clientes'))
            elif rol == 'vendedor':
                return redirect(url_for('usuarios.list_vendedores'))
            else:
                return redirect(url_for('auth.login'))

    # GET request
    return render_template('usuarios/registro.html',
                           rol=rol,
                           is_first_user=is_first_user)

@usuarios_bp.route('/list/supervisores')
@login_required
def list_supervisores():
    if current_user.role != 'administrador':
        return "No autorizado", 403
        
    supervisores = list(db.users.find({'role': 'supervisor', 'is_active': True}))
    
    return render_template('usuarios/supervisores.html', supervisores=supervisores)

@usuarios_bp.route('/nuevo/supervisor')
@login_required
def nuevo_supervisor():
    if current_user.role not in ['administrador']:
        return "No autorizado", 403
        
    return redirect(url_for('usuarios.registro', rol='supervisor'))

@usuarios_bp.route('/nuevo/vendedor')
@login_required
def nuevo_vendedor():
    if current_user.role not in ['administrador']:
        return "No autorizado", 403
        
    return redirect(url_for('usuarios.registro', rol='vendedor'))

@usuarios_bp.route('/list/vendedores')
@login_required
def list_vendedores():
    if current_user.role not in ['administrador']:
        return "No autorizado", 403
        
    vendedores = list(db.users.find({'role': 'vendedor', 'is_active': True}))
    
    return render_template('usuarios/vendedores.html', vendedores=vendedores)

@usuarios_bp.route('/list/tecnicos')
@login_required
def list_tecnicos():
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
        
    tecnicos = list(db.users.find({'role': 'tecnico', 'is_active': True}))
    
    return render_template('usuarios/tecnicos.html', tecnicos=tecnicos)

@usuarios_bp.route('/nuevo/tecnico')
@login_required
def nuevo_tecnico():
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
        
    return redirect(url_for('usuarios.registro', rol='tecnico'))

@usuarios_bp.route('/list/clientes')
@login_required
def list_clientes():
    if current_user.role not in ['supervisor', 'administrador', 'vendedor']:
        return "No autorizado", 403
        
    page = int(request.args.get('page', 1))
    per_page = 20
    skip = (page - 1) * per_page

    clientes = list(
        db.users.find({'role': 'cliente', 'is_active': True})
        .sort('name', 1)
        .skip(skip)
        .limit(per_page)
    )
    
    return render_template('usuarios/clientes.html', clientes=clientes,
                       page=page,
                       per_page=per_page)

@usuarios_bp.route('/nuevo/cliente')
@login_required
def nuevo_cliente():
    if current_user.role not in ['supervisor', 'administrador', 'vendedor']:
        return "No autorizado", 403
        
    return redirect(url_for('usuarios.registro', rol='cliente'))

@usuarios_bp.route('/editar/<user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    # Verificar permisos
    if current_user.role not in ['administrador', 'supervisor'] and str(current_user.id) != user_id:
        flash("No tienes permisos para editar este usuario", "danger")
        return redirect(url_for('auth.login'))

    # Obtener usuario
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash("Usuario no encontrado", "danger")
            return redirect(url_for('usuarios.list_tecnicos'))
    except:
        flash("ID inválido", "danger")
        return redirect(url_for('auth.login'))

    # Renderizar formulario con datos
    return render_template('usuarios/registro.html',
                           rol=user['role'],
                           user=user,
                           editing=True)

@usuarios_bp.route('/eliminar/<user_id>', methods=['POST'])
@login_required
def eliminar_usuario(user_id):
    # Verificar permisos
    if current_user.role != 'administrador':
        return "No autorizado", 403
    
    try:
        # Obtener el usuario a eliminar
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash("Usuario no encontrado", "danger")
            return redirect(url_for('dashboard.administrador_dashboard'))
        
        # Soft delete (marcar como inactivo)
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_active': False}}
        )
        
        # Redirigir según el rol del usuario eliminado
        if user['role'] == 'cliente':
            flash(f"Cliente {user['name']} eliminado correctamente", "success")
            return redirect(url_for('usuarios.list_clientes'))
        elif user['role'] == 'tecnico':
            flash(f"Tecnico {user['name']} eliminado correctamente", "success")
            return redirect(url_for('usuarios.list_tecnicos'))
        elif user['role'] == 'supervisor':
            flash(f"Supervisor {user['name']} eliminado correctamente", "success")
            return redirect(url_for('usuarios.list_supervisores'))
        else:  # administrador u otros roles
            return redirect(url_for('dashboard.administrador_dashboard'))
    
    except Exception as e:
        print(f"Error al eliminar: {str(e)}")
        flash("Error al eliminar el usuario", "danger")
        return redirect(url_for('dashboard.administrador_dashboard'))

@usuarios_bp.route('/reset-password/<user_id>', methods=['GET','POST'])
@login_required
def reset_password(user_id):
    # Verificar permisos
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
    
    # Obtener el usuario
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        flash("Usuario no encontrado", "danger")
        return redirect(url_for('usuarios.list_clientes' if user['role'] == 'cliente' else 'usuarios.list_tecnicos' if user['role'] == 'tecnico' else 'usuarios.list_supervisores'))
    
    if request.method == 'POST':
        # Resetear a la cédula como contraseña
        cedula = user['cedula']
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'password': generate_password_hash(cedula, method='pbkdf2:sha256', salt_length=16),
                'password_changed': False,
            }}
        )
        
        flash(f"Contraseña de {user['name']} reseteada a su cédula", "success")
        
        # Redirigir según el rol
        if user['role'] == 'administrador':
            return redirect(url_for('dashboard.administrador_dashboard'))
        elif user['role'] == 'supervisor':
            return redirect(url_for('usuarios.list_supervisores'))
        elif user['role'] == 'tecnico':
            return redirect(url_for('usuarios.list_tecnicos'))
        else:  # cliente
            return redirect(url_for('usuarios.list_clientes'))
    
    # GET: mostrar ventana de confirmación simple
    return render_template('usuarios/confirm_reset.html', user=user)

@usuarios_bp.route('/administrador/borrar_tablas', methods=['GET', 'POST'])
@login_required
def borrar_tablas():
    # Verificar que sea administrador
    if current_user.role != 'administrador':
        return "No autorizado", 403
    
    # Obtener todas las colecciones (excluyendo las del sistema)
    colecciones = [col for col in db.list_collection_names() 
                   if not col.startswith('system.')]
    
    # Contar documentos por colección (para mostrar en el template)
    conteo_docs = {col: db[col].count_documents({}) for col in colecciones}
    
    if request.method == 'POST':
        # Obtener colecciones seleccionadas
        selected = request.form.getlist('colecciones')
        
        if not selected:
            flash("No se seleccionaron colecciones para borrar", "danger")
            return redirect(url_for('usuarios.borrar_tablas'))
        
        try:
            # Borrar cada colección seleccionada
            for col in selected:
                db[col].delete_many({})  # Borra todos los documentos
            
            flash(f"Tablas borradas: {', '.join(selected)}", "success")
            # Si borró users, enviar al home para que se cree el primer admin
            if 'users' in selected:
                return redirect(url_for('home'))  # o url_for('registro')            
            
            return redirect(url_for('dashboard.administrador_dashboard'))
            
        except Exception as e:
            flash(f"Error al borrar: {str(e)}", "danger")
            return redirect(url_for('usuarios/borrar_tablas'))
    
    # Mostrar template con lista de colecciones
    return render_template('usuarios/borrar_tablas.html', 
                          colecciones=colecciones,
                          conteo_docs=conteo_docs)