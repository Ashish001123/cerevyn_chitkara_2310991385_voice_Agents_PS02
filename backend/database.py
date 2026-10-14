import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "appointements.db")

def get_connection():
    """
    Creates and returns a connection to the SQLite database.
    row_factory = sqlite3.Row allows us to access columns by name:
    row['customer_name']
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database schema with the 4 required tables.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS providers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER NOT NULL,
        slot_date TEXT NOT NULL,      -- e.g. '2026-10-20'
        start_time TEXT NOT NULL,     -- e.g. '10:00'
        end_time TEXT NOT NULL,       -- e.g. '10:30'
        status TEXT NOT NULL DEFAULT 'available', -- 'available' or 'booked'
        FOREIGN KEY (provider_id) REFERENCES providers (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_code TEXT UNIQUE NOT NULL, -- e.g. 'BK-1001'
        customer_name TEXT NOT NULL,
        provider_id INTEGER NOT NULL,
        slot_id INTEGER UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'confirmed', -- 'confirmed' or 'cancelled'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (provider_id) REFERENCES providers (id),
        FOREIGN KEY (slot_id) REFERENCES slots (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,         -- 'BOOKED', 'CANCELLED', 'DOUBLE_BOOKING_PREVENTED'
        booking_code TEXT,
        slot_id INTEGER,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()
    print(" SQLite Database initialized successfully!")
if __name__ == "__main__":
    init_db()