from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_required
from app._init_ import mongo, db
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import ReturnDocument
from app.helpers import update_order_status, validate_object_id
import re
from app._init_ import cache


ordenes_bp = Blueprint('ordenes', __name__)

@ordenes_bp.route('/list')
@login_required
def list_ordenes():
    if current_user.role not in ['supervisor', 'administrador', 'vendedor']:
        return "No autorizado", 403
    
    from bson import ObjectId
    
    # Obtener parámetros de búsqueda
    tech_id = request.args.get('technician', '').strip()
    client_query = request.args.get('client', '').strip()
    status_filter = request.args.get('status', '').strip()
    plate_query = request.args.get('plate', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    clear_filters = request.args.get('clear', '').strip()
    
    # Si el usuario presiona el botón de limpiar, no aplicar filtros
    if clear_filters:
        tech_id = client_query = status_filter = plate_query = date_from = date_to = ''
    
    query = {'is_active': True}
    
    # Filtro por técnico
    if tech_id:
        try:
            tasks = list(db.service_tasks.find({
                'technician_id': ObjectId(tech_id)
            }, {'order_id': 1}))
            order_ids = [t['order_id'] for t in tasks]
            query['_id'] = {'$in': order_ids} if order_ids else {'$in': []}
        except:
            pass
    
    # Filtro por cliente
    if client_query:
        client_ids = [c['_id'] for c in db.users.find({
            'role': 'cliente',
            'is_active': True,
            'name': {'$regex': client_query, '$options': 'i'}
        })]
        try:
            client_by_id = db.users.find_one({
                'role': 'cliente',
                'is_active': True,
                '_id': ObjectId(client_query)
            })
            if client_by_id:
                client_ids.append(client_by_id['_id'])
        except:
            pass
        if client_ids:
            query['client_id'] = {'$in': client_ids}
    
    # Filtro por estado
    if status_filter:
        query['status'] = status_filter
    
    # Filtro por placa
    if plate_query:
        vehicle_ids = [v['_id'] for v in db.vehicles.find({
            'is_active': True,
            'plate': {'$regex': plate_query, '$options': 'i'}
        })]
        if vehicle_ids:
            query['vehicle_id'] = {'$in': vehicle_ids}

    # Filtros por fecha
    if date_from or date_to:
        date_query = {}
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_query['$gte'] = datetime.combine(date_from_dt, datetime.min.time())
            except:
                pass
                
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_query['$lte'] = datetime.combine(date_to_dt, datetime.min.time()) + timedelta(days=1)
            except:
                pass
                
        if date_query:
            query['created_at'] = date_query
    
    # Buscar órdenes
# Paginación
    page = int(request.args.get('page', 1))
    per_page = 20
    skip = (page - 1) * per_page

    ordenes = list(
        db.service_orders.find(query)
        .sort('created_at', -1)
        .skip(skip)
        .limit(per_page)
    )
    
    # Poblar datos para cada orden
    for order in ordenes:
        if order.get('client_id'):
            client = db.users.find_one({
                '_id': ObjectId(order['client_id']),
                'role': 'cliente',
                'is_active': True
            })
            order['client_name'] = client.get('name', 'Sin nombre') if client else 'Sin nombre'
    
        if order.get('vehicle_id'):
            vehicle = db.vehicles.find_one({
                '_id': ObjectId(order['vehicle_id']),
                'is_active': True
            })
            order['vehicle_plate'] = vehicle.get('plate', 'Sin placa') if vehicle else 'Sin placa'
            order['vehicle_make'] = vehicle.get('make', 'Sin marca') if vehicle else 'Sin marca'
            order['vehicle_model'] = vehicle.get('model', 'Sin modelo') if vehicle else 'Sin modelo'
    
        tasks = list(db.service_tasks.find({'order_id': order['_id']}))
        order['tasks'] = []
        for t in tasks:
            tech = db.users.find_one({
                '_id': t['technician_id'],
                'is_active': True
            })
            order['tasks'].append({
                'technician_name': tech['name'] if tech else 'Sin técnico'
            })
    
    tecnicos = list(db.users.find({'role': 'tecnico', 'is_active': True}))
    
    return render_template(
        'ordenes/ordenes.html',
        orders=ordenes,
        tecnicos=tecnicos,
        tech_id=tech_id,
        client_query=client_query,
        status_filter=status_filter,
        plate_query=plate_query,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page
    )

@ordenes_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def nueva_orden():
    # Validación: Solo admins pueden saltarse esta regla
    if current_user.role not in ['administrador', 'supervisor', 'vendedor']:
        # Verificar si hay técnicos disponibles
        if db.users.count_documents({'role': 'tecnico'}) == 0:
            flash("⚠️ No hay técnicos creados. Crea al menos un técnico.", "danger")
            return redirect(url_for('dashboard.supervisor_dashboard'))
    
    if current_user.role not in ['supervisor', 'administrador', 'vendedor']:
        return "No autorizado", 403
    
    if request.method == 'POST':
        quick_search = request.form.get('quick_search', '').strip()
        
        # Validar placa (solo alfanuméricos y guiones)
        if not re.match(r'^[A-Za-z0-9-]+$', quick_search):
            flash("Formato de placa inválido. Solo se permiten letras, números y guiones.", "danger")
            return redirect(url_for('ordenes.nueva_orden'))        
        # **NUEVO: Generar número de orden con contador atómico**
        try:
            monthly_counter, yearly_counter, year, month = get_order_counters()
        
        # **NUEVO: Formato correcto con ceros a la izquierda**
            order_number = f"ORD-{year}-{month:02d}-{monthly_counter:04d}-{yearly_counter:06d}"
        
        except Exception as e:
        # Manejar error (ej: inicializar contadores)
            return str(e), 500
        
        # Buscar vehículo por placa
        vehicle = db.vehicles.find_one({'plate': quick_search})
        if vehicle:
            vehicle_id = vehicle['_id']
            
            # **NUEVO: Buscar cliente activo en relations**
            client_id = None
            if 'relations' in vehicle and vehicle['relations']:
                for relation in vehicle['relations']:
                    if relation.get('is_active', False):
                        client_id = relation.get('client_id')
                        break
            
            # Obtener datos del cliente si existe
            client = None
            if client_id:
                client = db.users.find_one({'_id': ObjectId(client_id)})
                
        else:
            # Crear nuevo vehículo temporal
            new_vehicle = {
                'plate': quick_search,
                'relations': [],
                "is_active": True,
                'created_at': datetime.now()
            }
            result = db.vehicles.insert_one(new_vehicle)
            cache.delete('admin_stats')
            vehicle_id = result.inserted_id
            client_id = None
        
        # Crear orden con estado según si hay cliente
        order = {
            "order_number": order_number,
            "client_id": client_id,
            "vehicle_id": vehicle_id,
            "description": f"Orden rápida: {quick_search}",
            "status": "pending",
            "registration_status": "completed" if client_id else "pending",
            "quick_search": quick_search,
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "created_by": ObjectId(current_user.id),
        }
        # ✅ Asignar vendedor si el usuario es vendedor
        if current_user.role == 'vendedor':
            order['assigned_vendor_id'] = ObjectId(current_user.id)  # Convertir a ObjectId       
        # Insertar orden
        result = db.service_orders.insert_one(order)
        order_id = result.inserted_id
        from app.services.audit import log_action
        log_action(current_user.name, "CREAR_ORDEN", f"order_id={order_id} plate={quick_search}") 
        cache.delete('admin_stats')
        
        return redirect(url_for('ordenes.detalle_orden', order_id=order_id))
    
    # GET: mostrar formulario  
    return render_template('ordenes/nueva_orden.html')

@ordenes_bp.route('/eliminar/<order_id>', methods=['POST'])
@login_required
def eliminar_orden(order_id):
    if current_user.role != 'administrador':
        return "No autorizado", 403
    update_order_status
    db.service_orders.update_one(
        {'_id': ObjectId(order_id)},
        {'$set': {'is_active': False}}
    )
    cache.delete('admin_stats')
    from app.services.audit import log_action
    log_action(current_user.name, "ELIMINAR_ORDEN", f"order_id={order_id}")    
    return redirect(url_for('ordenes.list_ordenes'))

@ordenes_bp.route('/actualizar-estado/<order_id>')
@login_required
def actualizar_estado_orden(order_id):
    if current_user.role not in ['supervisor', 'administrador', 'vendedor']:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    # Validar ID
    order_id = validate_object_id(order_id)
    
    # Actualizar estado basado en tareas
    update_order_status(order_id)
    
    # Obtener el estado actual para devolverlo
    order = db.service_orders.find_one({'_id': order_id})
    from app.services.audit import log_action
    log_action(current_user.name, "CAMBIAR_ESTADO_ORDEN", f"order_id={order_id} plate={quick_search}")
    return jsonify({'success': True, 'new_status': order['status']})

@ordenes_bp.route('/detalle/<order_id>', methods=['GET', 'POST'])
@login_required
def detalle_orden(order_id):
    # Roles que pueden acceder a esta vista
    if current_user.role not in ['supervisor', 'administrador', 'vendedor', 'cliente']:
        return "No autorizado", 403

    from_page = request.args.get('from_page', 'list_ordenes')  # Default a lista
    tecnico_id = request.args.get('tecnico_id', None)          # ✅ tu línea original

    # Obtener la orden
    order = db.service_orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        return "Orden no encontrada", 404

    # Cliente
    client = None
    if order.get('client_id'):
        try:
            client = db.users.find_one({'_id': ObjectId(order['client_id'])})
        except:
            client = None

    # Vehículo
    vehicle = None
    if order.get('vehicle_id'):
        try:
            vehicle = db.vehicles.find_one({'_id': ObjectId(order['vehicle_id'])})
        except:
            vehicle = None

    # Creador
    creator = None
    if order.get('created_by'):
        try:
            creator = db.users.find_one({'_id': ObjectId(order['created_by'])})
        except:
            creator = None

    # Tareas
    tasks = list(db.service_tasks.find({'order_id': order['_id']}))

    # Técnicos
    tecnicos = list(db.users.find({'role': 'tecnico', 'is_active': True}))

    # --- NUEVO: lista de vendedores y vendedor asignado ---
    vendedores = list(db.users.find({'role': 'vendedor', 'is_active': True}))
    assigned_vendor = None
    if order.get('assigned_vendor_id'):
        try:
            assigned_vendor = db.users.find_one({'_id': ObjectId(order['assigned_vendor_id'])})
        except:
            assigned_vendor = None

    # Técnico actual (si aplica)
    tecnico = None
    if current_user.role == 'tecnico':
        try:
            tecnico = db.users.find_one({'_id': ObjectId(current_user.id)})
            tecnico_id = str(tecnico['_id']) if tecnico else tecnico_id
        except:
            tecnico = None

    # Permisos
    can_edit_all = (current_user.role == 'administrador')
    can_edit_supervisor = (current_user.role == 'supervisor')
    can_add_tasks = (current_user.role in ['administrador', 'supervisor'])
    read_only = (current_user.role == 'cliente')

    # --- Manejo POST para asignar vendedor ---
    if request.method == 'POST' and current_user.role in ['administrador', 'supervisor']:
        vendedor_id = request.form.get('vendedor_id')
        if vendedor_id:
            try:
                vendedor_obj = ObjectId(vendedor_id)
                vendedor_user = db.users.find_one({'_id': vendedor_obj, 'role': 'vendedor', 'is_active': True})
                if vendedor_user:
                    db.service_orders.update_one(
                        {'_id': order['_id']},
                        {'$set': {'assigned_vendor': vendedor_obj, 'updated_at': datetime.now()}}
                    )
                    flash("Vendedor asignado correctamente.", "success")
                else:
                    flash("El vendedor seleccionado no es válido.", "danger")
            except Exception:
                flash("ID de vendedor inválido.", "danger")

        return redirect(url_for('ordenes.detalle_orden', order_id=order_id))

    # Render
    return render_template(
        'ordenes/detalle_orden.html',
        order=order,
        client=client,
        vehicle=vehicle,
        tasks=tasks,
        tecnicos=tecnicos,
        creator=creator,
        assigned_vendor=assigned_vendor,   # ✅ vendedor responsable actual
        vendedores=vendedores,             # ✅ lista de vendedores
        from_page=from_page,
        tecnico_id=tecnico_id,
        tecnico=tecnico,
        can_edit_all=can_edit_all,
        can_edit_supervisor=can_edit_supervisor,
        can_add_tasks=can_add_tasks,
        read_only=read_only
    )




@ordenes_bp.route('/agregar-tarea/<order_id>', methods=['POST'])
@login_required
def agregar_tarea(order_id):
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
    
    task_description = request.form.get('task_description')
    technician_id = request.form.get('technician_id')
    
    if not task_description or not technician_id:
        flash("Descripción de tarea y técnico son requeridos")
        return redirect(url_for('ordenes.detalle_orden', order_id=order_id))
    
    db.service_tasks.insert_one({
        'order_id': ObjectId(order_id),
        'technician_id': ObjectId(technician_id),
        'description': task_description,
        'status': 'pending',
        'start_time': None,
        'end_time': None,
        'observations': '',
        'created_at': datetime.now()
    })
    
    flash("Tarea agregada correctamente", "success")
    return redirect(url_for('ordenes.detalle_orden', order_id=order_id))

@ordenes_bp.route('/tareas-tecnico')
@login_required
def tareas_tecnico():
    if current_user.role not in ['tecnico', 'supervisor', 'administrador']:
        return "No autorizado", 403
    
    # Obtener técnico actual
    technician = db.users.find_one({'_id': ObjectId(current_user.id)})
    
    # Pipeline más completo
    pipeline = [
        {'$match': {'technician_id': technician['_id']}},
        {'$lookup': {
            'from': 'service_orders',
            'localField': 'order_id',
            'foreignField': '_id',
            'as': 'order'
        }},
        {'$unwind': '$order'},
        {'$lookup': {
            'from': 'vehicles',
            'localField': 'order.vehicle_id',
            'foreignField': '_id',
            'as': 'vehicle'
        }},
        {'$unwind': '$vehicle'},
        {'$project': {
            '_id': 1,
            'description': 1,
            'status': 1,
            'start_time': 1,
            'end_time': 1,
            'order_number': '$order.order_number',
            'vehicle_plate': '$vehicle.plate',
            'vehicle_make': '$vehicle.make'
        }}
    ]
    
    tareas = list(db.service_tasks.aggregate(pipeline))
    
    return render_template('ordenes/tareas_tecnico.html', 
                         tareas=tareas,
                         technician=technician)

@ordenes_bp.route('/ver-tecnico/<order_id>')
@login_required
def ver_orden_tecnico(order_id):
    if current_user.role not in ['supervisor', 'administrador', 'tecnico']:
        return "No autorizado", 403
    
    # Obtener la orden con todos los datos
    order = db.service_orders.find_one({'_id': ObjectId(order_id)})
    # Obtener datos relacionados
    client = db.users.find_one({'_id': order['client_id']})
    vehicle = db.vehicles.find_one({'_id': order['vehicle_id']})
    
    # Obtener tareas de la orden asignadas al técnico
    technician = db.users.find_one({'_id': ObjectId(current_user.id)})
    tasks = list(db.service_tasks.find({
        'order_id': ObjectId(order_id),
        'technician_id': technician['_id']
    }))
    return render_template('ordenes/tecnico_orden.html', 
                          order=order, 
                          client=client, 
                          vehicle=vehicle, 
                          tasks=tasks)

@ordenes_bp.route('/actualizar-tareas-tecnico/<order_id>', methods=['POST'])
@login_required
def actualizar_tareas_tecnico(order_id):
    if current_user.role not in ['supervisor', 'administrador', 'tecnico']:
        return "No autorizado", 403
    
    # Obtener técnico actual
    technician = db.technicians.find_one({'user_id': ObjectId(current_user.id)})
    
    # Procesar cada tarea
    for key, value in request.form.items():
        if key.startswith('task-'):
            task_id = key.split('-')[1]
            status = value
            observations = request.form.get(f'obs-{task_id}', '')
            
            # Actualizar tarea
            db.service_tasks.update_one(
                {'_id': ObjectId(task_id)},
                {'$set': {
                    'status': status,
                    'observations': observations,
                    'updated_at': datetime.now()
                }}
            )
    
    # Actualizar estado de la orden
    update_order_status(ObjectId(order_id))
    
    flash("Tareas actualizadas correctamente", "success")
    return redirect(url_for('ordenes.ver_orden_tecnico', order_id=order_id))

@ordenes_bp.route('/ver-tarea/<task_id>')
@login_required
def ver_tarea(task_id):
    if current_user.role not in ['supervisor', 'administrador', 'tecnico']:
        return "No autorizado", 403
    
    task = db.service_tasks.find_one({'_id': ObjectId(task_id)})
    
    # Obtener datos relacionados
    order = db.service_orders.find_one({'_id': task['order_id']})
    client = db.users.find_one({'_id': order['client_id']})
    vehicle = db.vehicles.find_one({'_id': order['vehicle_id']})
    
    return render_template('ordenes/ver_tarea.html', task=task, order=order, client=client, vehicle=vehicle)

# Actualizar tarea
@ordenes_bp.route('/tecnico/tarea/<order_id>/actualizar', methods=['POST'])
@login_required
def actualizar_tarea(order_id):
    # Verificar que el usuario sea técnico o supervisor
    user_role = current_user.role
    if user_role not in ['tecnico', 'supervisor','administrador']:
        return "No autorizado", 403
    
    # Verificar que la tarea existe y pertenece al técnico (si es técnico)
    task = db.service_tasks.find_one({'_id': ObjectId(order_id)})
    if not task:
        return "Tarea no encontrada", 404
    
    if user_role == 'tecnico':
        technician = db.users.find_one({'user_id': ObjectId(current_user.id), 'role':'tecnico'})
        if str(task['technician_id']) != str(technician['_id']):
            return "No autorizado", 403
    
    # Actualizar tarea
    status = request.form.get('status')
    observations = request.form.get('observations')
    task_description = request.form.get('task_description')  # Nuevo campo
    if not task_description:
        flash("La descripción de la tarea es requerida")
        return redirect(url_for('detalle_orden', order_id=str(task['order_id'])))
    update_data = {
        'status': status,
        'observations': observations,
        'description': task_description,  # Actualizar descripción        
        'updated_at': datetime.now()
    }
    
    db.service_tasks.update_one(
        {'_id': ObjectId(order_id)},
        {'$set': update_data}
    )
    
    # Actualizar estado de la orden
    update_order_status(task['order_id'])
    
    flash("Tarea actualizada correctamente", "success")
    return redirect(url_for('detalle_orden', order_id=str(task['order_id'])))


@ordenes_bp.route('/cliente/<client_id>')
@login_required
def ordenes_cliente(client_id):
    if current_user.role != 'cliente':
        return "No autorizado", 403
    
    # Obtener el cliente actual
    client = db.users.find_one({
        '_id': ObjectId(client_id),
        'role': 'cliente'
    })
    
    if not client:
        return "Cliente no encontrado", 404
    
    # Obtener órdenes del cliente
    ordenes = db.service_orders.aggregate([
        {
            '$match': {'client_id': client['_id']}
        },
        {
            '$lookup': {
                'from': 'vehicles',
                'localField': 'vehicle_id',
                'foreignField': '_id',
                'as': 'vehicle'
            }
        },
        {
            '$unwind': '$vehicle'
        }
    ])
    
    return render_template('ordenes/cliente.html', ordenes=ordenes)

# Funciones auxiliares
def update_order_status(order_id):
    """Actualiza el estado de una orden basado en sus tareas"""
    # Obtener todas las tareas de la orden
    tasks = list(db.service_tasks.find({'order_id': order_id}))
    
    if not tasks:
        # Si no hay tareas, el estado es "pending"
        db.service_orders.update_one(
            {'_id': order_id},
            {'$set': {'status': 'pending'}}
        )
        cache.delete('admin_stats')

        return
    
    # Determinar estado basado en tareas
    all_completed = all(task['status'] == 'completed' for task in tasks)
    has_in_progress = any(task['status'] == 'in_progress' for task in tasks)
    has_pending = any(task['status'] == 'pending' for task in tasks)
    
    if all_completed:
        new_status = 'completed'
    elif has_in_progress:
        new_status = 'in_progress'
    else:
        new_status = 'pending'
    
    # Actualizar orden
    db.service_orders.update_one(
        {'_id': order_id},
        {'$set': {'status': new_status, 'updated_at': datetime.now()}}
    )
    cache.delete('admin_stats')


def get_order_counters():
    """
    Retorna los contadores para generar el número de orden:
    - monthly_counter: reinicia cada mes
    - yearly_counter: reinicia cada año
    """
    now = datetime.now()
    year, month = now.year, now.month
    counters = db.order_counters

    # 1️⃣ Contador anual
    # Crear documento si no existe
    counters.update_one(
        {'_id': f'year:{year}'},
        {'$setOnInsert': {'year': year, 'yearly_counter': 0}},
        upsert=True
    )
    # Incrementar
    year_doc = counters.find_one_and_update(
        {'_id': f'year:{year}'},
        {'$inc': {'yearly_counter': 1}},
        return_document=ReturnDocument.AFTER
    )
    yearly_counter = year_doc['yearly_counter']

    # 2️⃣ Contador mensual
    # Crear documento si no existe
    counters.update_one(
        {'_id': f'month:{year}-{month:02d}'},
        {'$setOnInsert': {'year': year, 'month': month, 'monthly_counter': 0}},
        upsert=True
    )
    # Incrementar
    month_doc = counters.find_one_and_update(
        {'_id': f'month:{year}-{month:02d}'},
        {'$inc': {'monthly_counter': 1}},
        return_document=ReturnDocument.AFTER
    )
    monthly_counter = month_doc['monthly_counter']

    return monthly_counter, yearly_counter, year, month


@ordenes_bp.route("/ordenes/detalles/<orden_id>")
@login_required
def detalles_orden(orden_id):
    orden = mongo.db.service_orders.find_one({"_id": ObjectId(orden_id)})
    if not orden:
        return "<p class='text-danger'>Orden no encontrada</p>"

    cliente = db.users.find_one({"_id": orden.get("cliente_id")})
    tecnicos = list(db.users.find({"_id": {"$in": orden.get("tecnicos_ids", [])}}))

    return render_template("ordenes/detalles_ordenes.html", orden=orden, cliente=cliente, tecnicos=tecnicos)


@ordenes_bp.route('/actualizar-tareas/<order_id>', methods=['POST'])
@login_required
def actualizar_tareas_orden(order_id):
    if current_user.role not in ['supervisor', 'administrador', 'vendedor']:
        return "No autorizado", 403

    # 1) Eliminar tareas marcadas
    delete_ids = request.form.getlist('delete_task_ids')
    for tid in delete_ids:
        try:
            db.service_tasks.delete_one({'_id': ObjectId(tid)})
        except:
            continue

    # 2) Actualizar tareas existentes
    for key, value in request.form.items():
        if key.startswith('task-') and key.endswith('-desc'):
            task_id = key.split('-')[1]
            desc = value

            # Inicializar update_data con la descripción y timestamp
            update_data = {'description': desc, 'updated_at': datetime.now()}

            # Verificar y agregar campos presentes en el formulario
            status_key = f'task-{task_id}-status'
            if status_key in request.form:
                update_data['status'] = request.form[status_key]

            obs_key = f'task-{task_id}-obs'
            if obs_key in request.form:
                update_data['observations'] = request.form[obs_key]

            tech_key = f'task-{task_id}-tech'
            if tech_key in request.form:
                tech = request.form[tech_key]
                if tech:
                    update_data['technician_id'] = ObjectId(tech)
                else:
                    # Opcional: Manejar técnico vacío si es permitido
                    pass

            # Actualizar solo si hay cambios
            if len(update_data) > 2:  # Al menos un campo adicional además de descripción y timestamp
                db.service_tasks.update_one(
                    {'_id': ObjectId(task_id)},
                    {'$set': update_data}
                )

    # 3) Crear nuevas tareas (código original)
        # Insertar técnico "Sin asignar" si no existe
    if not db.users.find_one({'name': 'Sin asignar', 'role': 'tecnico'}):
        db.users.insert_one({
            'name': 'Sin asignar',
            'role': 'tecnico',
            'is_active': True,
        # ... otros campos requeridos
    })
    for key, value in request.form.items():
        if key.startswith('new-task-') and key.endswith('-desc'):
            desc = value
            tech = request.form.get(key.replace('-desc', '-tech'))
            if desc:  # Solo verificamos que haya descripción
                # Usar técnico "Sin asignar" si no se seleccionó
                if not tech:
                    # Buscar técnico "Sin asignar"
                    default_tech = db.users.find_one({
                        'name': 'Sin asignar',
                        'role': 'tecnico',
                        'is_active': True
                    })
                    if default_tech:
                        tech = str(default_tech['_id'])
                    else:
                        flash("⚠️ Técnico 'Sin asignar' no encontrado", "warning")
                        continue
                
                # Insertar tarea
                db.service_tasks.insert_one({
                    'order_id': ObjectId(order_id),
                    'technician_id': ObjectId(tech),
                    'description': desc,
                    'status': 'pending',
                    'observations': '',
                    'start_time': None,
                    'end_time': None,
                    'created_at': datetime.now()
                })

    # Actualizar estado general de la orden
    update_order_status(ObjectId(order_id))

    flash("Tareas actualizadas correctamente", "success")
    from_page = request.args.get("from_page") or request.form.get("from_page")
    from app.services.audit import log_action
    log_action(current_user.name, "ACTUALIZAR_TAREAS", f"order_id={order_id}")
    return redirect(url_for('ordenes.detalle_orden', order_id=order_id, from_page=from_page))

@ordenes_bp.route('/reasignar_vendedor/<order_id>', methods=['POST'])
@login_required
def reasignar_vendedor(order_id):
    if current_user.role not in ['administrador', 'supervisor']:
        return "No autorizado", 403

    vendor_id = request.form.get('vendor_id')
    if not vendor_id:
        flash("Debe seleccionar un vendedor válido", "warning")
        return redirect(url_for('ordenes.detalle_orden', order_id=order_id))

    try:
        db.service_orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"assigned_vendor_id": ObjectId(vendor_id)}}
        )
        flash("Vendedor asignado correctamente", "success")
    except Exception as e:
        flash(f"Error al asignar vendedor: {str(e)}", "danger")

    return redirect(url_for('ordenes.detalle_orden', order_id=order_id))
