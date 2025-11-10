const backendApiUrl = '/api'; // Apunta a la ruta proxied por Nginx
let qrScanner = null; // Variable global para la instancia del escáner
let currentEventId = null; // ID del evento actual para la validación

// --- Funciones de Utilidad ---
function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

function showSection(sectionId) {
    document.getElementById('mainContent').style.display = 'none';
    document.getElementById('validationContent').style.display = 'none';
    document.getElementById(sectionId).style.display = 'block';
}

// --- Inicialización y Enrutamiento ---
document.addEventListener('DOMContentLoaded', () => {
    const eventIdParam = getQueryParam('event_id');
    if (eventIdParam) {
        currentEventId = eventIdParam;
        showValidationView(currentEventId);
    } else {
        showEventManagementView();
        loadEvents();
    }
});

// --- Vista de Gestión de Eventos ---
function showEventManagementView() {
    showSection('mainContent');
    stopQrScanner(); // Asegurarse de que el escáner esté detenido si se vuelve a la gestión
    document.getElementById('stopScannerButton').style.display = 'none';
}

// --- Vista de Validación de Tickets ---
async function showValidationView(eventId) {
    showSection('validationContent');
    document.getElementById('stopScannerButton').style.display = 'block';
    document.getElementById('validationResult').textContent = ''; // Limpiar resultados anteriores

    // Obtener y mostrar detalles del evento
    try {
        const response = await fetch(`${backendApiUrl}/events/${eventId}`);
        const eventData = await response.json();
        if (response.ok) {
            document.getElementById('currentEventName').textContent = eventData.name;
            document.getElementById('currentEventDate').textContent = eventData.event_date;
        } else {
            document.getElementById('validationHeader').textContent = `Error: Evento ${eventId} no encontrado.`;
        }
    } catch (error) {
        document.getElementById('validationHeader').textContent = `Error al cargar detalles del evento ${eventId}.`;
        console.error("Error fetching event details:", error);
    }

    initializeAndStartQrScanner();
}

// --- Crear Evento ---
document.getElementById('createEventForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('eventName').value;
    const event_date = document.getElementById('eventDate').value;
    const location = document.getElementById('eventLocation').value;
    const eventResponseDiv = document.getElementById('eventResponse');
    eventResponseDiv.className = 'info';
    eventResponseDiv.textContent = 'Creando evento...';

    try {
        const response = await fetch(`${backendApiUrl}/events`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, event_date, location })
        });

        const data = await response.json();
        if (response.ok) {
            eventResponseDiv.className = 'success';
            eventResponseDiv.innerHTML = `Evento "${data.event.name}" creado con éxito.<br>
                                            Link de Validación: <a href="${data.event.validation_link}" target="_blank">${window.location.origin}${data.event.validation_link}</a>
                                            <button onclick="copyToClipboard('${window.location.origin}${data.event.validation_link}')">Copiar Link</button>`;
            document.getElementById('createEventForm').reset();
            loadEvents(); // Recargar la lista de eventos
        } else {
            eventResponseDiv.className = 'error';
            eventResponseDiv.textContent = `Error al crear evento: ${data.error || response.statusText}`;
        }
    } catch (error) {
        eventResponseDiv.className = 'error';
        eventResponseDiv.textContent = `Error de conexión: ${error.message}`;
        console.error("Error creating event:", error);
    }
});

// --- Cargar Eventos ---
async function loadEvents() {
    const eventsList = document.getElementById('eventsList');
    eventsList.innerHTML = '<li>Cargando eventos...</li>';
    try {
        const response = await fetch(`${backendApiUrl}/events`);
        const events = await response.json();
        eventsList.innerHTML = ''; // Limpiar mensaje de carga

        if (events.length === 0) {
            eventsList.innerHTML = '<li>No hay eventos creados.</li>';
            return;
        }

        events.forEach(event => {
            const li = document.createElement('li');
            li.innerHTML = `
                <div>
                    <h3>${event.name}</h3>
                    <p>Fecha: ${event.event_date}</p>
                    <p>Ubicación: ${event.location || 'N/A'}</p>
                    <p>ID: ${event.id}</p>
                </div>
                <div class="event-actions">
                    <button onclick="openCreateTicketModal(${event.id}, '${event.name}', '${event.event_date}')">Dar de Alta Clientes</button>
                    <button onclick="copyToClipboard('${window.location.origin}${event.validation_link}')">Copiar Link de Validación</button>
                    <button onclick="window.location.href='${event.validation_link}'">Ir a Validación</button>
                </div>
            `;
            eventsList.appendChild(li);
        });
    } catch (error) {
        eventsList.innerHTML = '<li class="error">Error al cargar eventos.</li>';
        console.error("Error loading events:", error);
    }
}

// --- Funciones para el Modal de Crear Tickets ---
const createTicketModal = document.getElementById('createTicketModal');
const closeButton = document.querySelector('.close-button');
const modalEventName = document.getElementById('modalEventName');
const modalEventId = document.getElementById('modalEventId');
const createTicketForm = document.getElementById('createTicketForm');
const ticketResponse = document.getElementById('ticketResponse');

closeButton.onclick = () => {
    createTicketModal.style.display = 'none';
}

window.onclick = (event) => {
    if (event.target == createTicketModal) {
        createTicketModal.style.display = 'none';
    }
}

function openCreateTicketModal(eventId, eventName, eventDate) {
    modalEventName.textContent = `Crear Tickets para: ${eventName} (${eventDate})`;
    modalEventId.value = eventId;
    ticketResponse.className = 'info';
    ticketResponse.textContent = ''; // Limpiar mensaje anterior
    createTicketForm.reset(); // Limpiar formulario del modal
    createTicketModal.style.display = 'block';
}

createTicketForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const event_id = document.getElementById('modalEventId').value;
    const user_id = document.getElementById('ticketUserId').value;
    const seat = document.getElementById('ticketSeat').value;

    ticketResponse.className = 'info';
    ticketResponse.textContent = 'Generando ticket...';

    try {
        const payload = { event_id, seat };
        if (user_id) { // Solo añadir user_id si no está vacío
            payload.user_id = user_id;
        }

        const response = await fetch(`${backendApiUrl}/ticket/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ticket_${event_id}_${user_id || 'generado'}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            ticketResponse.className = 'success';
            ticketResponse.textContent = 'Ticket generado y PDF descargado con éxito.';
            createTicketForm.reset(); // Limpiar formulario del modal
        } else {
            const errorData = await response.json();
            ticketResponse.className = 'error';
            ticketResponse.textContent = `Error al generar ticket: ${errorData.error || response.statusText}`;
        }
    } catch (error) {
        ticketResponse.className = 'error';
        ticketResponse.textContent = `Error de conexión: ${error.message}`;
        console.error("Error al crear ticket:", error);
    }
});

// --- Funcionalidad de Escaneo y Validación QR ---
function initializeAndStartQrScanner() {
    if (typeof Html5Qrcode === 'undefined') {
        document.getElementById('validationResult').className = 'validation-info error';
        document.getElementById('validationResult').textContent = 'Error: La librería del escáner QR no se ha cargado correctamente.';
        return;
    }

    if (!qrScanner) {
        qrScanner = new Html5Qrcode("qr-reader");
    }

    if (qrScanner.isScanning) {
        console.log("Escáner ya está activo, no se necesita iniciar de nuevo.");
        return;
    }

    qrScanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        qrCodeSuccessCallback,
        (errorMessage) => {
            if (errorMessage.includes("NotAllowedError") || errorMessage.includes("NotFoundError") || errorMessage.includes("Permission denied")) {
                document.getElementById('validationResult').className = 'validation-info error';
                document.getElementById('validationResult').textContent = 'Error: No se pudo acceder a la cámara. Verifique permisos o si hay una cámara disponible.';
            }
        }
    ).catch(err => {
        document.getElementById('validationResult').className = 'validation-info error';
        document.getElementById('validationResult').textContent = `Error al iniciar el escáner QR. (Detalle: ${err.message || err})`;
    });
}

const qrCodeSuccessCallback = async (decodedText, decodedResult) => {
    console.log(`QR Scanned: ${decodedText}`);
    stopQrScanner();
    document.getElementById('validationResult').textContent = 'Validando QR...';

    try {
        const response = await fetch(`${backendApiUrl}/ticket/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qr_content: decodedText, event_id: currentEventId })
        });

        const data = await response.json();
        const validationResultDiv = document.getElementById('validationResult');

        if (response.ok) {
            if (data.ticket_info.scaned) {
                validationResultDiv.className = 'validation-info invalid'; // Usar invalid para ya escaneado
                validationResultDiv.textContent = `Ticket ya escaneado: ${data.ticket_info.scaned_at ? new Date(data.ticket_info.scaned_at).toLocaleString() : 'N/A'}. Pertenece a ${data.ticket_info.user_id}, Asiento: ${data.ticket_info.seat}`;
            } else {
                validationResultDiv.className = 'validation-info valid';
                validationResultDiv.innerHTML = `Ticket válido para el evento ${currentEventId}: <br>
                ID: ${data.ticket_info.id}<br>
                Usuario/Cliente: ${data.ticket_info.user_id}<br>
                Asiento: ${data.ticket_info.seat}`;

                // Marcar el ticket como escaneado
                await fetch(`${backendApiUrl}/ticket/update_scaned`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ qr_content: decodedText, event_id: currentEventId })
                });
            }
        } else {
            validationResultDiv.className = 'validation-info invalid';
            validationResultDiv.textContent = `Ticket inválido para este evento: ${data.message || response.statusText}`;
        }
    } catch (error) {
        document.getElementById('validationResult').className = 'validation-info error';
        document.getElementById('validationResult').textContent = `Error de conexión con la API: ${error.message}`;
        console.error("Error al validar ticket:", error);
    } finally {
        // Reanudar el escáner después de un breve retraso
        setTimeout(initializeAndStartQrScanner, 3000);
    }
};

function stopQrScanner() {
    if (qrScanner && qrScanner.isScanning) {
        qrScanner.stop().catch(err => {
            console.error("Error al detener el escáner QR:", err);
        });
    }
}

document.getElementById('stopScannerButton').addEventListener('click', () => {
    stopQrScanner();
    document.getElementById('validationResult').textContent = 'Escáner detenido.';
    document.getElementById('stopScannerButton').style.display = 'none';
});

// --- Funciones de Portapapeles ---
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('¡Enlace copiado al portapapeles!');
    }).catch(err => {
        console.error('Error al copiar el texto: ', err);
        alert('No se pudo copiar el enlace. Por favor, cópielo manualmente: ' + text);
    });
}