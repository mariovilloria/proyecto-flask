from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_required
from app import mongo
from datetime import datetime
from bson import ObjectId
from app import db

vehiculos_bp = Blueprint('vehiculos', __name__)

def update_order_registration_status(order_id, client_id):
    """Actualiza el client_id y estado de registro de una orden."""
    # Convertir client_id a ObjectId si es necesario
    if client_id:
        client_id = ObjectId(client_id)
    
    # Buscar la orden
    order = db.service_orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        return
    
    # Si la orden tiene client_id = null, actualizar
    if not order.get('client_id'):
        db.service_orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {
                'client_id': client_id,
                'registration_status': 'completed' if client_id else 'pending'
            }}
        )

@vehiculos_bp.route('/list')
@login_required
def list_vehiculos():
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
    
    # Obtener vehículos
    page = int(request.args.get('page', 1))
    per_page = 20
    skip = (page - 1) * per_page

    vehiculos = list(
        db.vehicles.find({'is_active': True})
        .sort('plate', 1)
        .skip(skip)
        .limit(per_page)
    )
    # Preparar datos para el template
    for vehiculo in vehiculos:
        # Obtener todas las relaciones activas
        active_relations = [
            rel for rel in vehiculo.get('relations', []) 
            if rel.get('is_active', False)
        ]
        
        # Obtener datos de clientes para cada relación
        relations_info = []
        for rel in active_relations:
            # Buscar cliente en la colección unificada de usuarios
            client = db.users.find_one({
                '_id': rel['client_id'],
                'role': 'cliente'  # Filtrar por rol cliente
            })
            if client:
                relations_info.append({
                    'type': rel['relation_type'],
                    'name': client.get('name', 'Sin nombre')  # El nombre está en el usuario
                })
        
        # Agregar al vehículo
        vehiculo['relations_info'] = relations_info
    
    return render_template('vehiculos/vehiculos.html', vehiculos=vehiculos,
                       page=page,
                       per_page=per_page)

@vehiculos_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_vehiculo():
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
    
    if request.method == 'POST':
        # Obtener datos del formulario
        plate = request.form.get('plate')
        make = request.form.get('make')
        model = request.form.get('model')
        year = int(request.form.get('year')) if request.form.get('year') else None
        color = request.form.get('color')
        
        # Obtener datos de relaciones
        client_id = request.form.get('client_id')
        relation_type = request.form.get('relation_type')
        
        # Crear documento de vehículo
        vehicle = {
            "plate": plate,
            "make": make,
            "model": model,
            "year": year,
            "color": color,
            'is_active': True,
            "relations": [
                {
                    "client_id": ObjectId(client_id),
                    "relation_type": relation_type,
                    "is_active": True,
                    "start_date": datetime.now()
                }
            ]
        }
        
        # Insertar en la base de datos
        db.vehicles.insert_one(vehicle)
        
        flash("Vehículo registrado correctamente", "success")
        return redirect(url_for('vehiculos.list_vehiculos'))
    
    # GET: mostrar formulario
    clientes = list(db.users.find({'role': 'cliente'}))
    return render_template('vehiculos/nuevo_vehiculo.html', clientes=clientes)

@vehiculos_bp.route("/vehiculos/<vehicle_id>")
@login_required
def ver_vehiculo(vehicle_id):
    vehiculo = db.vehicles.find_one({"_id": ObjectId(vehicle_id)})
    if not vehiculo:
        flash("Vehículo no encontrado", "danger")
        return redirect(url_for("vehiculos.list_vehiculos"))

    ordenes = []
    for orden in db.service_orders.find({"vehicle_id": ObjectId(vehicle_id)}):  # 👈 aquí la corrección
        cliente = db.users.find_one({"_id": orden.get("client_id")})  # 👈 en tu código era cliente_id
        ordenes.append({
            **orden,
            "cliente": cliente["name"] if cliente else "No asignado"
        })

    return render_template("vehiculos/ver_vehiculo.html", vehiculo=vehiculo, ordenes=ordenes)

@vehiculos_bp.route('/editar/<vehicle_id>', methods=['GET', 'POST'])
@login_required
def editar_vehiculo(vehicle_id):
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
    
    # Obtener vehículo
    vehicle = db.vehicles.find_one({'_id': ObjectId(vehicle_id)})
    if not vehicle:
        return "Vehículo no encontrado", 404
    
    # Buscar cliente actual
    current_relation = None
    if 'relations' in vehicle and vehicle['relations']:
        for relation in vehicle['relations']:
            if relation.get('is_active', False):
                current_relation = relation
                break
    next_url = request.args.get('next', url_for('vehiculos.list_vehiculos'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        plate = request.form.get('plate')
        make = request.form.get('make')
        model = request.form.get('model')
        year = int(request.form.get('year')) if request.form.get('year') else None
        color = request.form.get('color')
        client_id = request.form.get('client_id')
        relation_type = request.form.get('relation_type')
        
        # Actualizar datos básicos
        db.vehicles.update_one(
            {'_id': ObjectId(vehicle_id)},
            {'$set': {
                'plate': plate,
                'make': make,
                'model': model,
                'year': year,
                'color': color
            }}
        )
        
        if client_id:
            # Buscar órdenes con el mismo vehicle_id y client_id = null
            orders = list(db.service_orders.find({
                'vehicle_id': ObjectId(vehicle_id),
                'client_id': None
            }))
            
            # Actualizar cada orden
            for order in orders:
                update_order_registration_status(order['_id'], client_id)
            
            # Crear nueva relación
            new_relation = {
                'client_id': ObjectId(client_id),
                'relation_type': relation_type,
                'is_active': True,
                'start_date': datetime.now()
            }
            
            # Si ya hay relaciones, actualizar la activa
            if 'relations' in vehicle:
                # Desactivar todas las relaciones
                for relation in vehicle['relations']:
                    relation['is_active'] = False
                
                # Buscar si ya existe una relación con este cliente
                relation_updated = False
                for relation in vehicle['relations']:
                    if str(relation['client_id']) == client_id:
                        relation['is_active'] = True
                        relation['relation_type'] = relation_type
                        relation['start_date'] = datetime.now()
                        relation_updated = True
                        break
                
                # Si no existe, agregar la nueva relación
                if not relation_updated:
                    vehicle['relations'].append(new_relation)
                
                # Guardar las relaciones actualizadas
                db.vehicles.update_one(
                    {'_id': ObjectId(vehicle_id)},
                    {'$set': {'relations': vehicle['relations']}}
                )
            else:
                # Si no hay relaciones, crear el array
                db.vehicles.update_one(
                    {'_id': ObjectId(vehicle_id)},
                    {'$set': {'relations': [new_relation]}}
                )
        
        flash("Vehículo actualizado correctamente", "success")
        return redirect(next_url)
    
    # GET: mostrar formulario
    clientes = list(db.users.find({'role': 'cliente'}))
    return render_template('vehiculos/editar_vehiculo.html', 
                          vehiculo=vehicle, 
                          current_relation=current_relation,
                          clientes=clientes)

@vehiculos_bp.route('/eliminar/<vehicle_id>')
@login_required
def eliminar_vehiculo(vehicle_id):
    if current_user.role != 'administrador':
        return "No autorizado", 403
    
    db.vehicles.update_one(
        {'_id': ObjectId(vehicle_id)},
        {'$set': {'is_active': False}}
    )
    return redirect(url_for('vehiculos.list_vehiculos'))

@vehiculos_bp.route('/get-clients/<vehicle_id>')
@login_required
def get_vehicle_clients(vehicle_id):
    try:
        vehicle = db.vehicles.find_one({'_id': ObjectId(vehicle_id)})
        if not vehicle:
            return jsonify([])
        # Obtener relaciones del vehículo
        active_relations = [
            rel for rel in vehicle.get('relations', []) 
            if rel.get('is_active', False)
        ]
        
        # Construir lista de clientes
        clients = []
        for rel in active_relations:
            client = db.users.find_one({'_id': rel['client_id']})
            if client:
                clients.append({
                    '_id': str(client['_id']),
                    'name': client.get('name', 'Sin nombre'),
                    'relation_type': rel.get('relation_type', 'Sin tipo')
                })
        
        return jsonify(clients)
    
    except Exception as e:
        print(f"Error en endpoint clientes: {str(e)}")
        return jsonify([])
    
@vehiculos_bp.route("/ordenes/detalles/<order_id>")
@login_required
def detalle_orden(order_id):
    orden = db.service_orders.find_one({"_id": ObjectId(order_id)})
    if not orden:
        return "<p class='text-danger'>Orden no encontrada</p>"

    # Buscar cliente
    cliente = None
    if orden.get("client_id"):
        cliente = db.users.find_one({"_id": orden["client_id"]})

    # Buscar vehículo
    vehiculo = None
    if orden.get("vehicle_id"):
        vehiculo = db.vehicles.find_one({"_id": orden["vehicle_id"]})

    # Renderizar un fragmento HTML para el modal
    return render_template("ordenes/detalles_ordenes.html", 
                           orden=orden, cliente=cliente, vehiculo=vehiculo)
