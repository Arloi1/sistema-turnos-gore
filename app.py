from flask import Flask, render_template, request, redirect, jsonify
from datetime import datetime
from urllib.parse import unquote
import os
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

database_url = os.environ.get('DATABASE_URL', 'postgresql://turnos_user:tKEDL05OtBzDYWxtBJzjD8trXumanuci@dpg-d9lo31tg1s2s739u3n90-a/turnos_db_dcxx')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

OPERADORES = {"Ventanilla 01": "Jhoe", "Ventanilla 02": "Sandra"}
estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0}


class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(50))
    nombre = db.Column(db.String(100))
    fecha_registro = db.Column(db.String(50))
    estado = db.Column(db.String(50))
    turno = db.Column(db.Integer)

class HistorialAtencion(db.Model):
    __tablename__ = 'historial_atenciones'
    id = db.Column(db.Integer, primary_key=True)
    ventanilla = db.Column(db.String(100))
    turno = db.Column(db.Integer)
    fecha = db.Column(db.DateTime, default=datetime.now)
    dni = db.Column(db.String(50))

with app.app_context():
    db.create_all()

# RUTA PARA ACTUALIZAR LOS TURNOS EN LA PANTALLA DE LA TV
@app.route('/actualizar_turno/<ventanilla>', methods=['GET', 'POST'])
def actualizar_turno(ventanilla):
    global estado_visual
    v_nombre = unquote(ventanilla)
    
    if v_nombre in estado_visual:
        ticket = Ticket.query.filter_by(estado="ESPERA").order_by(Ticket.id.asc()).first()
        
        if not ticket:
            return jsonify({"status": "vacio"}), 200
        
        turno_real = ticket.turno
        dni_ciudadano = ticket.dni
        
        ticket.estado = "ATENDIDO"
        
        nuevo_historial = HistorialAtencion(
            ventanilla=v_nombre,
            turno=turno_real,
            fecha=datetime.now(),
            dni=dni_ciudadano
        )
        db.session.add(nuevo_historial)
        
        estado_visual[v_nombre] = turno_real
        db.session.commit()
        
        return jsonify({"status": "ok", "ventanilla": v_nombre, "turno": turno_real})
    return jsonify({"status": "error"}), 400

# RUTA DE LAS ESTADÍSTICAS MOSTRADAS EN EL HISTORIAL DE ATENCIONES
@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    filtro = request.args.get('filtro')
    query = db.session.query(HistorialAtencion.ventanilla, db.func.count(HistorialAtencion.id).label('total'))
    
    if filtro == 'dia': 
        # Compatible con la fecha actual según el motor
        if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI']:
            query = query.filter(db.func.date(HistorialAtencion.fecha) == db.func.current_date())
        else:
            query = query.filter(db.func.date(HistorialAtencion.fecha) == db.func.date('now'))
    elif filtro == 'mes':
        if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI']:
            query = query.filter(db.extract('month', HistorialAtencion.fecha) == db.extract('month', db.func.current_date()))
        else:
            query = query.filter(db.func.strftime('%m', HistorialAtencion.fecha) == db.func.strftime('%m', 'now'))
            
    registros = query.group_by(HistorialAtencion.ventanilla).all()
    return jsonify([{"ventanilla": r.ventanilla, "colaborador": OPERADORES.get(r.ventanilla), "total": r.total} for r in registros])
    
# RUTA PARA LIMPIAR BASE DE DATOS
@app.route('/limpiar_base_datos_secreto')
def limpiar_db():
    global estado_visual
    try:
        Ticket.query.delete()
        HistorialAtencion.query.delete()
        db.session.commit()
        # Reiniciar los contadores visuales a 0
        estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0}
        return "¡Base de datos y contadores reiniciados a 0 con éxito!"
    except Exception as e:
        return f"Error: {e}"

# RUTA PARA HISTORIAL
@app.route('/historial', methods=['GET'])
def historial():
    try:
        registros = HistorialAtencion.query.order_by(HistorialAtencion.id.desc()).all()
        return render_template('historial.html', registros=registros)
    except Exception as e:
        # Si hay algún error con la tabla, la recrea automáticamente y evita el pantallazo rojo
        db.create_all()
        return render_template('historial.html', registros=[])

# RUTA PARA OBTENER LOS TURNOS 
@app.route('/obtener_todos_los_turnos', methods=['GET'])
def obtener_todos(): 
    return jsonify(estado_visual)

# RUTA PARA RESETEAR LOS TURNOS 
@app.route('/resetear_turnos', methods=['POST'])
def resetear_turnos():
    global estado_visual
    estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0}
    return jsonify({"status": "reseteado"})


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        dni = request.form.get('dni')
        if dni:
            max_t = db.session.query(db.func.max(Ticket.turno)).scalar()
            nuevo_turno = (max_t or 0) + 1
            nuevo_ticket = Ticket(
                dni=dni,
                nombre="Ciudadano",
                fecha_registro=datetime.now().strftime("%d/%m/%Y %H:%M"),
                estado='ESPERA',
                turno=nuevo_turno
            )
            db.session.add(nuevo_ticket)
            db.session.commit()
            return redirect('/')
    
    tickets = Ticket.query.filter_by(estado="ESPERA").order_by(Ticket.id.asc()).all()
    return render_template('index.html', tickets=tickets)

# RUTA PARA EL CONTROL DEL CAMBIO DE TURNOS
@app.route('/control')
def control(): 
    return render_template('control.html')

# RUTA PARA MOSTRAR EN LA PANTALLA DE LA TV
@app.route('/pantalla')
def pantalla(): 
    return render_template('pantalla.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
