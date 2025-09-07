from datetime import datetime
from bson import ObjectId
from flask import abort, jsonify
from app import db

def update_order_status(order_id):
    """
    Actualiza el estado de una orden basado en el estado de sus tareas.
    """
    # Obtener todas las tareas de la orden
    tasks = list(db.service_tasks.find({'order_id': order_id}))
    
    if not tasks:
        # Sin tareas, mantener como pending
        db.service_orders.update_one(
            {'_id': order_id},
            {'$set': {'status': 'pending'}}
        )
        return
    
    # Determinar el estado general
    statuses = [task.get('status', 'pending') for task in tasks]
    
    if 'completed' in statuses:
        if all(status == 'completed' for status in statuses):
            # Todas las tareas completadas
            db.service_orders.update_one(
                {'_id': order_id},
                {'$set': {'status': 'completed'}}
            )
        else:
            # Algunas tareas completadas, otras no
            db.service_orders.update_one(
                {'_id': order_id},
                {'$set': {'status': 'in_progress'}}
            )
    else:
        # Sin tareas completadas
        db.service_orders.update_one(
            {'_id': order_id},
            {'$set': {'status': 'pending'}}
        )

def get_order_counters():
    """
    Genera y devuelve contadores para números de orden.
    """
    from datetime import datetime
    
    # Obtener fecha actual
    now = datetime.now()
    year = now.year
    month = now.month
    
    # Colección para contadores
    counter_coll = db.orders_counter
    
    # Verificar/crear contador mensual
    monthly_counter = counter_coll.find_one_and_update(
        {'type': 'monthly', 'year': year, 'month': month},
        {'$inc': {'count': 1}},
        upsert=True,
        return_document=True
    ).get('count', 1)
    
    # Verificar/crear contador anual
    yearly_counter = counter_coll.find_one_and_update(
        {'type': 'yearly', 'year': year},
        {'$inc': {'count': 1}},
        upsert=True,
        return_document=True
    ).get('count', 1)
    
    return monthly_counter, yearly_counter, year, month

def validate_object_id(object_id):
    """
    Valida y convierte un ID a ObjectId, abortando si es inválido.
    """
    try:
        return ObjectId(object_id)
    except:
        abort(400, "ID inválido")