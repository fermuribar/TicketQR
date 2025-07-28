-- Tabla de eventos
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    event_date DATE NOT NULL,
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de tickets (modificada para incluir event_id)
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, -- Clave foránea al evento
    user_id VARCHAR(255), -- Ahora puede ser opcional o generado
    seat VARCHAR(50) NOT NULL,
    qr_content VARCHAR(255) UNIQUE NOT NULL,
    scaned BOOLEAN DEFAULT FALSE,
    scaned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);