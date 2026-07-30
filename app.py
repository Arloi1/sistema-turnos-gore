from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
from datetime import datetime
from urllib.parse import unquote
import os
from flask import Flask

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

OPERADORES = {"Ventanilla 01": "Jhoe", "Ventanilla 02": "Sandra"}

estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0}

def get_db():
    conn = sqlite3.connect('tickets.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS tickets 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  dni TEXT, nombre TEXT, fecha_registro TEXT, estado TEXT, turno INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS historial_atenciones 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ventanilla TEXT, turno INTEGER, fecha TIMESTAMP, dni TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/actualizar_turno/<ventanilla>', methods=['GET', 'POST'])
def actualizar_turno(ventanilla):
    global estado_visual
    v_nombre = unquote(ventanilla)
    
    if v_nombre in estado_visual:
        conn = get_db()
        ticket = conn.execute('SELECT id, turno, dni FROM tickets WHERE estado="ESPERA" ORDER BY id ASC LIMIT 1').fetchone()
        
        if not ticket:
            conn.close()
            return jsonify({"status": "vacio"}), 200
        
        turno_real = ticket['turno']
        dni_ciudadano = ticket['dni']
        
        conn.execute('UPDATE tickets SET estado="ATENDIDO" WHERE id=?', (ticket['id'],))
        
        conn.execute('INSERT INTO historial_atenciones (ventanilla, turno, fecha, dni) VALUES (?, ?, ?, ?)', 
                     (v_nombre, turno_real, datetime.now(), dni_ciudadano))
        
        estado_visual[v_nombre] = turno_real
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok", "ventanilla": v_nombre, "turno": turno_real})
    return jsonify({"status": "error"}), 400

@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    filtro = request.args.get('filtro')
    conn = get_db()
    query = 'SELECT ventanilla, COUNT(*) as total FROM historial_atenciones WHERE 1=1 '
    if filtro == 'dia': query += " AND date(fecha) = date('now')"
    elif filtro == 'mes': query += " AND strftime('%m', fecha) = strftime('%m', 'now')"
    query += " GROUP BY ventanilla"
    registros = conn.execute(query).fetchall()
    conn.close()
    return jsonify([{"ventanilla": r['ventanilla'], "colaborador": OPERADORES.get(r['ventanilla']), "total": r['total']} for r in registros])

# RUTA PARA HISTORIAL
@app.route('/historial', methods=['GET'])
def historial():
    conn = get_db()
    registros = conn.execute('SELECT * FROM historial_atenciones ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('historial.html', registros=registros)

@app.route('/obtener_todos_los_turnos', methods=['GET'])
def obtener_todos(): return jsonify(estado_visual)

@app.route('/resetear_turnos', methods=['POST'])
def resetear_turnos():
    global estado_visual
    estado_visual = {"Ventanilla 01": 0, "Ventanilla 02": 0}
    return jsonify({"status": "reseteado"})

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db()
    if request.method == 'POST':
        dni = request.form.get('dni')
        if dni:
            last = conn.execute('SELECT MAX(turno) as max_t FROM tickets').fetchone()
            nuevo_turno = (last['max_t'] or 0) + 1
            conn.execute('INSERT INTO tickets (dni, nombre, fecha_registro, estado, turno) VALUES (?, ?, ?, ?, ?)', 
                         (dni, "Ciudadano", datetime.now().strftime("%d/%m/%Y %H:%M"), 'ESPERA', nuevo_turno))
            conn.commit()
            return redirect('/')
    
    tickets = conn.execute('SELECT * FROM tickets WHERE estado="ESPERA" ORDER BY id ASC').fetchall()
    conn.close()
    return render_template('index.html', tickets=tickets)

@app.route('/control')
def control(): return render_template('control.html')

@app.route('/pantalla')
def pantalla(): return render_template('pantalla.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
