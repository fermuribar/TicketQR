import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS # Importa CORS
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
CORS(app) # Habilita CORS para todas las rutas de la aplicación

# Configuración de la base de datos (usando variables de entorno de docker-compose)
DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'clubdb')
DB_USER = os.getenv('DB_USER', 'user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

def get_db_connection():
    # Asegúrate de que el backend pueda conectarse a la DB antes de la primera solicitud
    # Esto puede requerir un bucle de reintentos en un entorno de producción para mayor robustez
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

@app.route('/ticket/create', methods=['POST'])
def create_ticket():
    data = request.json
    user_id = data.get('user_id')
    event_date_str = data.get('event_date')
    seat = data.get('seat')

    if not all([user_id, event_date_str, seat]):
        return jsonify({"error": "Faltan datos: user_id, event_date, seat"}), 400

    try:
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    # Generar un contenido único para el QR
    qr_content = str(uuid.uuid4())

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tickets (user_id, event_date, seat, qr_content) VALUES (%s, %s, %s, %s) RETURNING id;",
            (user_id, event_date, seat, qr_content)
        )
        ticket_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

        # Generar QR y PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Información del ticket en el PDF
        c.drawString(50, height - 50, f"Ticket para el Club Deportivo")
        c.drawString(50, height - 70, f"ID de Ticket: {ticket_id}")
        c.drawString(50, height - 90, f"Usuario: {user_id}")
        c.drawString(50, height - 110, f"Evento: {event_date.strftime('%d/%m/%Y')}")
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

        return send_file(buffer, download_name=f'ticket_{ticket_id}.pdf', mimetype='application/pdf')

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/ticket/validate', methods=['POST'])
def validate_ticket():
    data = request.json
    qr_content = data.get('qr_content')

    if not qr_content:
        return jsonify({"error": "Contenido QR no proporcionado"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM tickets WHERE qr_content = %s;", (qr_content,))
        ticket = cur.fetchone()
        cur.close()
        conn.close()

        if ticket:
            return jsonify({
                "status": "valid",
                "message": "Ticket válido",
                "ticket_info": {
                    "id": ticket['id'],
                    "user_id": ticket['user_id'],
                    "event_date": ticket['event_date'].strftime('%Y-%m-%d'),
                    "seat": ticket['seat'],
                    "scaned": ticket['scaned'],
                    "scaned_at": ticket['scaned_at'].strftime('%Y-%m-%d %H:%M:%S') if ticket['scaned_at'] else None
                }
            }), 200
        else:
            return jsonify({"status": "invalid", "message": "Ticket no encontrado o inválido"}), 404

    except psycopg2.Error as e:
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/ticket/update_tiked_scaned', methods=['POST'])
def update_ticket_scaned():
    data = request.json
    qr_content = data.get('qr_content')

    if not qr_content:
        return jsonify({"error": "Contenido QR no proporcionado"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tickets SET scaned = TRUE, scaned_at = NOW() WHERE qr_content = %s RETURNING id;", (qr_content,))
        updated_ticket_id = cur.fetchone()

        if updated_ticket_id:
            conn.commit()
            cur.close()
            return jsonify({"status": "success", "message": "Ticket actualizado como escaneado", "ticket_id": updated_ticket_id[0]}), 200
        else:
            return jsonify({"status": "error", "message": "Ticket no encontrado o ya escaneado"}), 404

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Error de base de datos: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)