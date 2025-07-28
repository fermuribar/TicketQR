import os
from flask import Flask, request, jsonify, send_file, url_for
from flask_cors import CORS
import psycopg2
from psycopg2.extras import DictCursor
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import uuid
from datetime import datetime
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
CORS(app)

# Configuración de la base de datos
DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'clubdb')
DB_USER = os.getenv('DB_USER', 'user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

@app.route('/')
def home():
    return "Backend API del Club Deportivo"

# --- Endpoints para Eventos ---

@app.route('/events', methods=['POST'])
def create_event():
    data = request.json
    name = data.get('name')
    event_date_str = data.get('event_date')
    location = data.get('location')

    if not all([name, event_date_str]):
        return jsonify({"error": "Faltan datos: name, event_date"}), 400

    try:
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events (name, event_date, location) VALUES (%s, %s, %s) RETURNING id;",
            (name, event_date, location)
        )
        event_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        # Generar el link de validación para este evento
        # Nota: El host del frontend se manejará en el frontend JS o Nginx
        validation_link = f"/validate?event_id={event_id}" # Este es un path relativo que el frontend manejará

        return jsonify({
            "status": "success",
            "message": "Evento creado con éxito",
            "event": {
                "id": event_id,
                "name": name,
                "event_date": event_date.strftime('%Y-%m-%d'),
                "location": location,
                "validation_link": validation_link
            }
        }), 201

    except psycopg2.Error as e:
        if conn: conn.rollback()
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn: conn.close()

@app.route('/events', methods=['GET'])
def get_all_events():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, name, event_date, location, created_at FROM events ORDER BY event_date DESC, created_at DESC;")
        events = cur.fetchall()
        cur.close()
        conn.close()

        events_list = []
        for event in events:
            # Construir el link de validación para cada evento
            validation_link = f"/validate?event_id={event['id']}"
            events_list.append({
                "id": event['id'],
                "name": event['name'],
                "event_date": event['event_date'].strftime('%Y-%m-%d'),
                "location": event['location'],
                "created_at": event['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                "validation_link": validation_link
            })
        return jsonify(events_list), 200

    except psycopg2.Error as e:
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn: conn.close()

@app.route('/events/<int:event_id>', methods=['GET'])
def get_event_details(event_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, name, event_date, location, created_at FROM events WHERE id = %s;", (event_id,))
        event = cur.fetchone()
        cur.close()
        conn.close()

        if event:
            validation_link = f"/validate?event_id={event['id']}"
            return jsonify({
                "id": event['id'],
                "name": event['name'],
                "event_date": event['event_date'].strftime('%Y-%m-%d'),
                "location": event['location'],
                "created_at": event['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                "validation_link": validation_link
            }), 200
        else:
            return jsonify({"error": "Evento no encontrado"}), 404

    except psycopg2.Error as e:
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn: conn.close()

# --- Endpoints para Tickets (Modificados) ---

@app.route('/ticket/create', methods=['POST'])
def create_ticket():
    data = request.json
    event_id = data.get('event_id')
    user_id = data.get('user_id') # Opcional: si no se provee, se genera
    seat = data.get('seat')

    if not all([event_id, seat]):
        return jsonify({"error": "Faltan datos: event_id, seat"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)

        # Verificar si el evento existe
        cur.execute("SELECT id FROM events WHERE id = %s;", (event_id,))
        if not cur.fetchone():
            return jsonify({"error": "El evento especificado no existe"}), 404

        # Si user_id no se proporciona, generar uno simple. Por ejemplo, UUID o Ticket ID.
        # Para cumplir con "ID autoincremental para clientes" (donde el cliente es el ticket-holder):
        # El `id` del ticket ya es autoincremental. Si user_id es solo un identificador de 'cliente'
        # que no necesita ser globalmente único, podemos dejarlo en blanco o generarlo.
        # Generemos un UUID para user_id si no se provee, para que sea único pero no auto-incremental.
        # Si el usuario quiere un `id` numérico autoincremental para CADA cliente, necesitaríamos una tabla `clients`.
        # Por ahora, asumamos que "ID autoincremental" se refiere al `id` del propio ticket o un `user_id` generado.
        if not user_id:
            user_id = f"CLIENT-{uuid.uuid4().hex[:8].upper()}" # Generar un ID simple para el cliente/ticket-holder

        # Generar un contenido único para el QR
        qr_content = str(uuid.uuid4())

        cur.execute(
            "INSERT INTO tickets (event_id, user_id, seat, qr_content) VALUES (%s, %s, %s, %s) RETURNING id, user_id, event_id;",
            (event_id, user_id, seat, qr_content)
        )
        ticket_info = cur.fetchone()
        conn.commit()
        cur.close()

        ticket_id = ticket_info['id']
        generated_user_id = ticket_info['user_id']
        ticket_event_id = ticket_info['event_id']

        # Generar QR y PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Información del ticket en el PDF
        c.drawString(50, height - 50, f"Ticket para el Club Deportivo - Evento ID: {ticket_event_id}")
        c.drawString(50, height - 70, f"ID de Ticket: {ticket_id}")
        c.drawString(50, height - 90, f"Usuario/Cliente: {generated_user_id}")
        # Recuperar la fecha del evento para el PDF
        cur_pdf = conn.cursor(cursor_factory=DictCursor)
        cur_pdf.execute("SELECT name, event_date FROM events WHERE id = %s;", (ticket_event_id,))
        event_details_for_pdf = cur_pdf.fetchone()
        cur_pdf.close()
        if event_details_for_pdf:
            c.drawString(50, height - 110, f"Evento: {event_details_for_pdf['name']} ({event_details_for_pdf['event_date'].strftime('%d/%m/%Y')})")
        else:
            c.drawString(50, height - 110, f"Evento ID: {ticket_event_id} (Fecha no disponible)")

        c.drawString(50, height - 130, f"Asiento: {seat}")

        # Generar imagen QR
        qr_img = qrcode.make(qr_content)
        qr_img_buffer = BytesIO()
        qr_img.save(qr_img_buffer, format='PNG')
        qr_img_buffer.seek(0)

        # Convertir el buffer a ImageReader
        qr_img_reader = ImageReader(qr_img_buffer)

        # Dibujar QR en el PDF
        c.drawImage(qr_img_reader, width / 2 - 100, height - 300, width=200, height=200)
        c.drawString(50, height - 350, "Presente este QR para validación")

        c.save()
        buffer.seek(0)

        return send_file(buffer, download_name=f'ticket_event_{ticket_event_id}_user_{generated_user_id}.pdf', mimetype='application/pdf')

    except psycopg2.Error as e:
        if conn: conn.rollback()
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn: conn.close()

@app.route('/ticket/validate', methods=['POST'])
def validate_ticket():
    data = request.json
    qr_content = data.get('qr_content')
    event_id = data.get('event_id') # Ahora se requiere el ID del evento

    if not all([qr_content, event_id]):
        return jsonify({"error": "Faltan datos: qr_content, event_id"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM tickets WHERE qr_content = %s AND event_id = %s;", (qr_content, event_id))
        ticket = cur.fetchone()
        cur.close()
        conn.close()

        if ticket:
            return jsonify({
                "status": "valid",
                "message": "Ticket válido",
                "ticket_info": {
                    "id": ticket['id'],
                    "event_id": ticket['event_id'],
                    "user_id": ticket['user_id'],
                    "seat": ticket['seat'],
                    "qr_content": ticket['qr_content'],
                    "scaned": ticket['scaned'],
                    "scaned_at": ticket['scaned_at'].strftime('%Y-%m-%d %H:%M:%S') if ticket['scaned_at'] else None
                }
            }), 200
        else:
            return jsonify({"status": "invalid", "message": "Ticket no encontrado para este evento o inválido"}), 404

    except psycopg2.Error as e:
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn: conn.close()

@app.route('/ticket/update_scaned', methods=['POST']) # Renombrado de update_tiked_scaned
def update_ticket_scaned():
    data = request.json
    qr_content = data.get('qr_content')
    event_id = data.get('event_id') # Ahora se requiere el ID del evento

    if not all([qr_content, event_id]):
        return jsonify({"error": "Faltan datos: qr_content, event_id"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tickets SET scaned = TRUE, scaned_at = NOW() WHERE qr_content = %s AND event_id = %s RETURNING id;", (qr_content, event_id))
        updated_ticket_id = cur.fetchone()

        if updated_ticket_id:
            conn.commit()
            cur.close()
            return jsonify({"status": "success", "message": "Ticket actualizado como escaneado", "ticket_id": updated_ticket_id[0]}), 200
        else:
            return jsonify({"status": "error", "message": "Ticket no encontrado para este evento o ya escaneado"}), 404

    except psycopg2.Error as e:
        if conn: conn.rollback()
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)