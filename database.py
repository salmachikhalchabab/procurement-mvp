import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "procurement.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit_of_measure TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            raw_material_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id)
        );

        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            country TEXT NOT NULL,
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            contact_person TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number TEXT UNIQUE NOT NULL,
            product_id INTEGER,
            raw_material_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_of_measure TEXT NOT NULL,
            requested_date TEXT NOT NULL,
            requester TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id)
        );

        CREATE TABLE IF NOT EXISTS rfqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfq_number TEXT UNIQUE NOT NULL,
            pr_id INTEGER NOT NULL,
            vendor_id INTEGER,
            quotation_due_date TEXT NOT NULL,
            pdf_path TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pr_id) REFERENCES purchase_requests(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );
    """)

    # Add extra vendor columns if upgrading from old DB
    for col, definition in [
        ("phone",          "TEXT DEFAULT ''"),
        ("address",        "TEXT DEFAULT ''"),
        ("contact_person", "TEXT DEFAULT ''"),
    ]:
        try:
            c.execute(f"ALTER TABLE vendors ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()