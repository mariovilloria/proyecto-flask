from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from bson import ObjectId
import pymongo, calendar
from app._init_ import db, cache
from flask import current_app


dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/administrador')
@login_required
def administrador_dashboard():
    # Verificar que sea administrador
    if current_user.role != 'administrador':
        return "No autorizado", 403
    
    # Estadísticas optimizadas
    stats = cache.get('admin_stats')
    if stats is None:
        stats = get_optimized_stats()
        cache.set('admin_stats', stats, timeout=300)   # 5 minutos
    
    # Obtener datos para gráficos
    # Ventas/órdenes por mes
    
    # Obtener datos para los últimos 6 meses
    today = datetime.now()
    months_data = []
    
    for i in range(6):
        # Mes actual - i meses
        month_date = today - timedelta(days=30*i)
        year = month_date.year
        month = month_date.month
        
        # Nombre del mes
        month_name = calendar.month_name[month]
        
        # Contar órdenes del mes
        orders_count = db.service_orders.count_documents({
            'created_at': {
                '$gte': datetime(year, month, 1),
                '$lt': datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
            },
            'is_active': True
        })
        
        months_data.append({
            'month': month_name[:3],  # Jan, Feb, etc.
            'orders': orders_count
        })
    
    # Invertir para mostrar de más antiguo a más reciente
    months_data = months_data[::-1]
    
    # Estadísticas de técnicos
    tecnicos_stats = list(db.users.aggregate([
        {'$match': {'role': 'tecnico', 'is_active': True,'name': {'$ne': 'Sin asignar'}}},
        {'$lookup': {
            'from': 'service_tasks',
            'localField': '_id',
            'foreignField': 'technician_id',
            'as': 'tasks'
        }},
        {'$project': {
            'name': 1,
            'total_tasks': {'$size': '$tasks'},
            'completed_tasks': {
                '$size': {
                    '$filter': {
                        'input': '$tasks',
                        'as': 'task',
                        'cond': {'$eq': ['$$task.status', 'completed']}
                    }
                }
            }
        }}
    ]))
    return render_template(
        'dashboard/administrador_dashboard.html', 
        stats=stats,
        months_data=months_data,
        tecnicos_stats=tecnicos_stats
    )

@dashboard_bp.route('/tecnico')
@login_required
def tecnico_dashboard():
    if current_user.role not in ['tecnico', 'administrador']:
        return "No autorizado", 403
    
    # Obtener ID del técnico
    tecnico_id = ObjectId(current_user.id)
    
    # Pipeline para obtener órdenes con tareas del técnico
    pipeline = [
        {'$match': {'is_active': True}},
        {'$lookup': {
            'from': 'service_tasks',
            'localField': '_id',
            'foreignField': 'order_id',
            'as': 'tasks'
        }},
        {'$match': {
            'tasks.technician_id': tecnico_id
        }},
        {'$lookup': {
            'from': 'users',
            'localField': 'client_id',
            'foreignField': '_id',
            'as': 'client'
        }},
        {'$lookup': {
            'from': 'vehicles',
            'localField': 'vehicle_id',
            'foreignField': '_id',
            'as': 'vehicle'
        }}
    ]
    
    # Obtener órdenes
    orders = list(db.service_orders.aggregate(pipeline))
    
    # Crear conjuntos para evitar duplicados
    processed_order_ids = set()
    
    # Listas para categorizar
    pending_in_progress = []
    completed = []
    
    for order in orders:
        # Extraer cliente y vehículo
        order['client'] = order['client'][0] if order['client'] else {}
        order['vehicle'] = order['vehicle'][0] if order['vehicle'] else {}
        
        # Filtrar tareas del técnico
        tecnico_tasks = [task for task in order['tasks'] 
                        if str(task.get('technician_id')) == str(tecnico_id)]
        
        # Si ya procesamos esta orden, saltamos
        if str(order['_id']) in processed_order_ids:
            continue
            
        # Marcar como procesada
        processed_order_ids.add(str(order['_id']))
        
        # Verificar estado de tareas del técnico
        has_pending_in_progress = any(
            task['status'] in ['pending', 'in_progress'] 
            for task in tecnico_tasks
        )
        
        # Clasificar por estado de las tareas del técnico
        if has_pending_in_progress:
            # Orden en progreso para el técnico
            order['tasks'] = tecnico_tasks  # Solo tareas del técnico
            pending_in_progress.append(order)
        else:
            # Todas las tareas del técnico completadas
            order['tasks'] = tecnico_tasks
            completed.append(order)
    
    # Estadísticas del técnico (solo sus tareas)
    task_counts = {
        'pending': sum(1 for o in orders for t in o['tasks'] 
                      if t['status'] == 'pending' and str(t['technician_id']) == str(tecnico_id)),
        'in_progress': sum(1 for o in orders for t in o['tasks'] 
                          if t['status'] == 'in_progress' and str(t['technician_id']) == str(tecnico_id)),
        'completed': sum(1 for o in orders for t in o['tasks'] 
                        if t['status'] == 'completed' and str(t['technician_id']) == str(tecnico_id))
    }
    
    return render_template('dashboard/tecnico_dashboard.html', 
                          pending_in_progress=pending_in_progress,
                          completed=completed,
                          task_counts=task_counts)


@dashboard_bp.route('/supervisor')
@login_required
def supervisor_dashboard():
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    # Órdenes del día (pendientes y en progreso)
    today_orders = list(db.service_orders.find({
        'created_at': {
            '$gte': datetime.combine(today, datetime.min.time()),
            '$lt': datetime.combine(tomorrow, datetime.min.time())
        },
        'status': {'$in': ['pending', 'in_progress']},
        'is_active': True
    }))

    # Órdenes recientes completadas
    recent_orders = list(db.service_orders.find({
        'created_at': {
            '$gte': datetime.combine(today, datetime.min.time()),
            '$lt': datetime.combine(tomorrow, datetime.min.time())
        },
        'status': 'completed',
        'is_active': True
    }))

    # Enriquecer cada orden con vehículo y técnicos
    for order in today_orders + recent_orders:
        # Vehículo
        vehicle = db.vehicles.find_one({'_id': order.get('vehicle_id')}) if order.get('vehicle_id') else {}
        order['vehicle_make'] = vehicle.get('make', '')
        order['vehicle_model'] = vehicle.get('model', '')
        order['vehicle_color'] = vehicle.get('color', '')
        order['vehicle_plate'] = vehicle.get('plate', '')

        # Técnicos asignados
        tasks = list(db.service_tasks.find({'order_id': order['_id']}))
        technicians = []
        for t in tasks:
            tech = db.users.find_one({'_id': t.get('technician_id')}) if t.get('technician_id') else None
            if tech:
                technicians.append(tech['name'])
        order['technicians'] = technicians

    # Información de técnicos enriquecida (solo tareas de hoy)
    tecnicos = list(db.users.find({'role': 'tecnico', 'is_active': True,'name': {'$ne': 'Sin asignar'}}))
    tecnicos_info = []
    for tecnico in tecnicos:
        tid = tecnico.get('_id')

        # Construir query para cubrir ObjectId o string
        or_clauses = []
        if isinstance(tid, ObjectId):
            or_clauses.append({'technician_id': tid})
            or_clauses.append({'technician_id': str(tid)})
        else:
            or_clauses.append({'technician_id': tid})

        # Filtrar SOLO tareas del día actual
        tareas = list(db.service_tasks.find({
            '$or': or_clauses,
            'created_at': {
                '$gte': datetime.combine(today, datetime.min.time()),
                '$lt': datetime.combine(tomorrow, datetime.min.time())
            }
        }))

        # Normalizar y contar estados
        counts = {'pending': 0, 'in_progress': 0, 'completed': 0}
        for t in tareas:
            raw = (t.get('status') or '').lower()
            if 'complete' in raw:
                s = 'completed'
            elif 'progress' in raw or 'in progress' in raw:
                s = 'in_progress'
            elif 'pend' in raw:
                s = 'pending'
            else:
                s = 'pending'
            counts[s] += 1

        # Técnico ocupado si tiene algo pendiente o en progreso HOY
        busy = (counts['pending'] + counts['in_progress']) > 0

        # Ordenar tareas por fecha
        tareas_sorted = sorted(
            tareas,
            key=lambda x: x.get('created_at') if x.get('created_at') else datetime.min,
            reverse=True
        )

        tecnicos_info.append({
            '_id': tecnico.get('_id'),
            'name': tecnico.get('name', 'Sin nombre'),
            'counts': counts,
            'busy': busy,
            'tareas': tareas_sorted,
            'email': tecnico.get('email'),
            'phone': tecnico.get('phone')
        })

    # Estadísticas generales
    stats = {
        'total_orders': db.service_orders.count_documents({
            'created_at': {
                '$gte': datetime.combine(today, datetime.min.time()),
                '$lt': datetime.combine(tomorrow, datetime.min.time())
            },
            'is_active': True
        }),
        'active_orders': db.service_orders.count_documents({
            'status': 'in_progress',
            'is_active': True
        }),
        'completed_today': len(recent_orders),
        'pending_orders': db.service_orders.count_documents({
            'status': 'pending',
            'is_active': True
        })
    }

    user = db.users.find_one({'_id': ObjectId(current_user.id)})

    return render_template('dashboard/supervisor_dashboard.html',
                           user=user,
                           stats=stats,
                           today_orders=today_orders,
                           recent_orders=recent_orders,
                           tecnicos_info=tecnicos_info)


@dashboard_bp.route('/cliente')
@login_required
def cliente_dashboard():
    if current_user.role != 'cliente':
        return "No autorizado", 403
    
    # Obtener datos del cliente
    cliente = db.users.find_one({'_id': ObjectId(current_user.id)})
    
    # Obtener órdenes del cliente
    pipeline = [
        {'$match': {'client_id': ObjectId(current_user.id)}},
        {'$lookup': {
            'from': 'vehicles',
            'localField': 'vehicle_id',
            'foreignField': '_id',
            'as': 'vehicle'
        }},
        {'$unwind': '$vehicle'},
        {'$lookup': {
            'from': 'service_tasks',
            'localField': '_id',
            'foreignField': 'order_id',
            'as': 'tasks'
        }}
    ]
    
    ordenes = list(db.service_orders.aggregate(pipeline))
    
    # Calcular estado general
    stats = {
        'total': len(ordenes),
        'pending': sum(1 for o in ordenes if o['status'] == 'pending'),
        'in_progress': sum(1 for o in ordenes if o['status'] == 'in_progress'),
        'completed': sum(1 for o in ordenes if o['status'] == 'completed')
    }
    
    return render_template('dashboard/cliente_dashboard.html', 
                         cliente=cliente,
                         ordenes=ordenes,
                         stats=stats)


@dashboard_bp.route('/vendedor')
@login_required
def vendedor_dashboard():
    if current_user.role != 'vendedor':
        return "No autorizado", 403
    
    # Obtener datos del vendedor
    vendedor = db.users.find_one({'_id': ObjectId(current_user.id)})
    
    # ✅ ID del vendedor actual
    current_vendor_id = ObjectId(current_user.id)
    
    # ✅ Estadísticas: Órdenes asignadas al vendedor
    stats = {
        'total_clientes': db.users.count_documents({
            'role': 'cliente', 
            'is_active': True,
            'created_by': current_vendor_id  # Clientes que creó el vendedor
        }),
        'total_ordenes': db.service_orders.count_documents({
            'is_active': True,
            'assigned_vendor_id': current_vendor_id  # ✅ Solo órdenes asignadas
        }),
        'ordenes_pendientes': db.service_orders.count_documents({
            'status': 'pending', 
            'is_active': True,
            'assigned_vendor_id': current_vendor_id  # ✅ Filtrar por asignación
        }),
        'ordenes_progreso': db.service_orders.count_documents({
            'status': 'in_progress', 
            'is_active': True,
            'assigned_vendor_id': current_vendor_id  # ✅ Filtrar por asignación
        })
    }
    
    # ✅ Órdenes recientes: Solo asignadas al vendedor
    from datetime import datetime, timedelta
    fecha_limite = datetime.now() - timedelta(days=30)
    
    ordenes_recientes = list(db.service_orders.find({
        'created_at': {'$gte': fecha_limite},
        'is_active': True,
        'assigned_vendor_id': current_vendor_id  # ✅ Filtrar por asignación
    }).sort('created_at', -1).limit(5))
    
    # Poblar datos de clientes y vehículos (código existente)
    for orden in ordenes_recientes:
        if orden.get('client_id'):
            cliente = db.users.find_one({'_id': orden['client_id']})
            orden['cliente_nombre'] = cliente.get('name', 'Sin nombre') if cliente else 'Sin nombre'
        
        if orden.get('vehicle_id'):
            vehiculo = db.vehicles.find_one({'_id': orden['vehicle_id']})
            orden['vehiculo_placa'] = vehiculo.get('plate', 'Sin placa') if vehiculo else 'Sin placa'
    
    return render_template(
        'dashboard/vendedor_dashboard.html',
        stats=stats,
        ordenes_recientes=ordenes_recientes,
        vendedor=vendedor
    )


@dashboard_bp.route('/tecnico/detalle/<tecnico_id>', methods=['GET', 'POST'])
def tecnico_detalle(tecnico_id):
    if current_user.role not in ['supervisor', 'administrador']:
        return "No autorizado", 403
    
    # Obtener el técnico
    try:
        tecnico = db.users.find_one({'_id': ObjectId(tecnico_id)})
        if not tecnico or tecnico['role'] != 'tecnico':
            return "Técnico no válido", 404
    except:
        return "ID inválido", 400
    
    # Manejar fecha (por defecto hoy)
    fecha_str = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    try:
        fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d')
    except:
        fecha_dt = datetime.now()
    
    # Obtener órdenes del técnico en esa fecha
    start_date = datetime.combine(fecha_dt, datetime.min.time())
    end_date = start_date + timedelta(days=1)
    
    pipeline = [
        {'$match': {
            'created_at': {'$gte': start_date, '$lt': end_date},
            'is_active': True
        }},
        {'$lookup': {
            'from': 'service_tasks',
            'localField': '_id',
            'foreignField': 'order_id',
            'as': 'tasks'
        }},
        {'$match': {
            'tasks.technician_id': ObjectId(tecnico_id)
        }},
        {'$lookup': {
            'from': 'vehicles',
            'localField': 'vehicle_id',
            'foreignField': '_id',
            'as': 'vehicle'
        }}
    ]
    
    orders = list(db.service_orders.aggregate(pipeline))
    
    # Filtrar tareas del técnico
    for order in orders:
        order['tasks'] = [t for t in order['tasks'] 
                         if str(t['technician_id']) == tecnico_id]
        order['vehicle'] = order['vehicle'][0] if order['vehicle'] else {}
    
    # Estadísticas del día
    task_counts = {
        'pending': sum(1 for o in orders for t in o['tasks'] if t['status'] == 'pending'),
        'in_progress': sum(1 for o in orders for t in o['tasks'] if t['status'] == 'in_progress'),
        'completed': sum(1 for o in orders for t in o['tasks'] if t['status'] == 'completed')
    }
    
    return render_template(
        'dashboard/tecnico_detalle.html',
        tecnico=tecnico,
        orders=orders,
        fecha=fecha_dt,
        task_counts=task_counts,
        from_page='detalle_tecnico'
    )

def get_optimized_stats():
    """Obtiene estadísticas del dashboard admin con consultas optimizadas"""
    # Obtener conteo por roles en una sola consulta
    role_counts = {}
    pipeline = [
        {'$match': {'is_active': True}},
        {'$group': {
            '_id': '$role',
            'count': {'$sum': 1}
        }}
    ]
    for doc in db.users.aggregate(pipeline):
        role_counts[doc['_id']] = doc['count']
    
    # Total de usuarios
    total_users = db.users.count_documents({'is_active': True})
    
    # Obtener conteo de vehículos y órdenes
    total_vehicles = db.vehicles.count_documents({'is_active': True})
    total_orders = db.service_orders.count_documents({'is_active': True})
    
    # Órdenes recientes
    recent_orders = list(db.service_orders.find({
        'is_active': True, 
        'status': {'$in': ['in_progress', 'pending']}
    }).sort("created_at", -1).limit(5))
    
    # Poblar datos de clientes y vehículos
    for order in recent_orders:
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
    
    return {
        'total_users': total_users,
        'roles': {
            'administrador': role_counts.get('administrador', 0),
            'supervisor': role_counts.get('supervisor', 0),
            'tecnico': role_counts.get('tecnico', 0),
            'cliente': role_counts.get('cliente', 0),
            'vendedor': role_counts.get('vendedor', 0)
        },
        'total_vehicles': total_vehicles,
        'total_orders': total_orders,
        'recent_orders': recent_orders
    }