from flask import Flask, render_template, request, redirect, jsonify
from datetime import datetime
from urllib.parse import unquote
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

database_url = os.environ.get('DATABASE_URL', 'postgresql://turnos_user:tKEDL05OtBzDYWxtBJzjD8trXumanuci@dpg-d9lo31tg1s2s739u3n90-a/turnos_db_dcxx')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Asignación correcta de operadores por ventanilla
OPERADORES = {
    "Ventanilla 01": "Yajaira", 
    "Ventanilla 02": "Sandra", 
    "Ventanilla 03": "Jhoe"
}

estado_visual = {
    "Ventanilla 01": 0, 
    "Ventanilla 02": 0, 
    "Ventanilla 03": 0
}

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(50))
    nombre = db.Column(db.String(100))
    fecha_registro = db.Column(db.String(50))
    estado = db.Column(db.String(50))
    turno = db.Column(db.Integer)
    preferencial = db.Column(db.Boolean, default=False)

class HistorialAtencion(db.Model):
    __tablename__ = 'historial_atenciones'
    id = db.Column(db.Integer, primary_key=True)
    ventanilla = db.Column(db.String(100))
    turno = db.Column(db.Integer)
    fecha = db.Column(db.DateTime, default=datetime.now)
    dni = db.Column(db.String(50))

with app.app_context():
    db.create_all()
    # Solución automática para bases de datos existentes en Render que no tengan la columna preferencial
    try:
        db.session.execute(text('ALTER TABLE tickets ADD COLUMN IF NOT EXISTS preferencial BOOLEAN DEFAULT FALSE;'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Nota de migración automática:", e)

@app.route('/actualizar_turno/<ventanilla>', methods=['GET', 'POST'])
def actualizar_turno(ventanilla):
    global estado_visual
    v_nombre = unquote(ventanilla)
    
    if v_nombre in estado_visual:
        tipo = request.args.get('tipo', 'normal')
        
        ticket = None
        # Si llaman preferencial, busca primero un ticket marcado como preferencial en espera
        if tipo == 'preferencial':
            ticket = Ticket.query.filter_by(estado="ESPERA", preferencial=True).order_by(Ticket.id.asc()).first()
        
        # Si no hay preferencial o pidieron turno normal, toma el siguiente en orden estricto de llegada
        if not ticket:
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
        
        return jsonify({
            "status": "ok", 
            "ventanilla": v_nombre, 
            "turno": turno_real, 
            "es_preferencial": ticket.preferencial
        })
    return jsonify({"status": "error"}), 400

@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    filtro = request.args.get('filtro')
    query = db.session.query(HistorialAtencion.ventanilla, db.func.count(HistorialAtencion.id).label('total'))
    
    if filtro == 'dia':
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

@app.route('/historial', methods=['GET'])
def historial():
    try:
        registros = HistorialAtencion.query.order_by(HistorialAtencion.id.desc()).all()
        return render_template('historial.html', registros=registros)
    except Exception as e:
        db.create_all()
        return render_template('historial.html', registros=[])

@app.route('/obtener_todos_los_turnos', methods=['GET'])
def obtener_todos(): 
    # Devolvemos tanto el turno como el estado preferencial del último ticket atendido
    resultado = {}
    for v in ["Ventanilla 01", "Ventanilla 02", "Ventanilla 03"]:
        ultimo = HistorialAtencion.query.filter_by(ventanilla=v).order_by(HistorialAtencion.id.desc()).first()
        resultado[v] = ultimo.turno if ultimo else 0
    return jsonify(resultado)

@app.route('/resetear_turnos', methods=['POST'])
def resetear_turnos():
    global estado_visual
    estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0, "Ventanilla 03": 0}
    return jsonify({"status": "reseteado"})

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        dni = request.form.get('dni')
        preferencial = True if request.form.get('preferencial') == 'on' else False
        if dni:
            max_t = db.session.query(db.func.max(Ticket.turno)).scalar()
            nuevo_turno = (max_t or 0) + 1
            nuevo_ticket = Ticket(
                dni=dni,
                nombre="Ciudadano",
                fecha_registro=datetime.now().strftime("%d/%m/%Y %H:%M"),
                estado='ESPERA',
                turno=nuevo_turno,
                preferencial=preferencial
            )
            db.session.add(nuevo_ticket)
            db.session.commit()
            return redirect('/')
    
    tickets = Ticket.query.filter_by(estado="ESPERA").order_by(Ticket.id.asc()).all()
    return render_template('index.html', tickets=tickets)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        dni = request.form.get('dni')
        preferencial = True if request.form.get('preferencial') == 'on' else False
        if dni:
            max_t = db.session.query(db.func.max(Ticket.turno)).scalar()
            nuevo_turno = (max_t or 0) + 1
            nuevo_ticket = Ticket(
                dni=dni,
                nombre="Ciudadano",
                fecha_registro=datetime.now().strftime("%d/%m/%Y %H:%M"),
                estado='ESPERA',
                turno=nuevo_turno,
                preferencial=preferencial
            )
            db.session.add(nuevo_ticket)
            db.session.commit()
            return render_template('registro.html', mensaje="¡Turno generado con éxito!")
    return render_template('registro.html')

# Rutas independientes actualizadas para el control por cada operador
@app.route('/control')
def control_general(): 
    return render_template('control.html', operador='Sandra')

@app.route('/control/sandra')
def control_sandra():
    return render_template('control.html', operador='Sandra')

@app.route('/control/yajaira')
def control_yajaira():
    return render_template('control.html', operador='Yajaira')

@app.route('/control/jhoe')
def control_jhoe():
    return render_template('control.html', operador='Jhoe')

@app.route('/pantalla')
def pantalla(): 
    return render_template('pantalla.html')

@app.route('/limpiar_base_datos_secreto')
def limpiar_db():
    global estado_visual
    try:
        estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0, "Ventanilla 03": 0}
        db.session.execute(text('TRUNCATE TABLE tickets, historial_atenciones RESTART IDENTITY CASCADE;'))
        db.session.commit()
        return "¡Base de datos limpia, contadores en 0 e IDs reiniciados con éxito!"
    except Exception as e:
        db.session.rollback()
        return f"Error: {e}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
