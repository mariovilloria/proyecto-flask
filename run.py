from app._init_ import app, db

if __name__ == '__main__':
    try:
        db.users.create_index('cedula', unique=True)
        db.users.create_index('role')
        db.vehicles.create_index('plate', unique=True)
        db.service_orders.create_index([('created_at', -1)])
        db.service_orders.create_index('status')
        db.service_orders.create_index('client_id')
        db.service_orders.create_index('vehicle_id')
        db.service_orders.create_index('assigned_vendor_id')   # para vendedores
        db.service_tasks.create_index([('order_id', 1), ('technician_id', 1)])
        db.service_tasks.create_index('status')
        print("✅ Índices creados/verificados")
    except Exception as e:
        print("⚠️  Algunos índices ya existen:", e)
    app.run(debug=True)