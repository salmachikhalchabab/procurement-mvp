import sqlite3
import os
import bcrypt

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
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_materials (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            unit_of_measure TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bom (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id      INTEGER NOT NULL,
            raw_material_id INTEGER NOT NULL,
            quantity        REAL NOT NULL,
            FOREIGN KEY (product_id)      REFERENCES products(id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id)
        );

        CREATE TABLE IF NOT EXISTS vendors (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            email          TEXT NOT NULL,
            country        TEXT NOT NULL,
            phone          TEXT DEFAULT '',
            address        TEXT DEFAULT '',
            contact_person TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS purchase_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number       TEXT UNIQUE NOT NULL,
            product_id      INTEGER,
            raw_material_id INTEGER NOT NULL,
            quantity        REAL NOT NULL,
            unit_of_measure TEXT NOT NULL,
            requested_date  TEXT NOT NULL,
            requester       TEXT NOT NULL,
            notes           TEXT,
            status          TEXT DEFAULT 'Draft',
            created_by      INTEGER,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id),
            FOREIGN KEY (created_by)      REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS rfqs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            rfq_number         TEXT UNIQUE NOT NULL,
            pr_id              INTEGER NOT NULL,
            vendor_id          INTEGER,
            quotation_due_date TEXT NOT NULL,
            pdf_path           TEXT,
            status             TEXT DEFAULT 'Sent',
            created_at         TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pr_id)     REFERENCES purchase_requests(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name     TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'viewer',
            is_active     INTEGER DEFAULT 1,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pr_status_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_id      INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by INTEGER,
            note       TEXT,
            changed_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pr_id)      REFERENCES purchase_requests(id),
            FOREIGN KEY (changed_by) REFERENCES users(id)
        );
    """)

    # ── Migrations ────────────────────────────────────────
    migrations = [
        ("vendors",           "phone",          "TEXT DEFAULT ''"),
        ("vendors",           "address",        "TEXT DEFAULT ''"),
        ("vendors",           "contact_person", "TEXT DEFAULT ''"),
        ("purchase_requests", "created_by",     "INTEGER"),
        ("purchase_requests", "updated_at",     "TEXT DEFAULT (datetime('now'))"),
        ("rfqs",              "status",         "TEXT DEFAULT 'Sent'"),
    ]
    for table, col, definition in migrations:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # Migrate old status values
    c.execute("UPDATE purchase_requests SET status='Submitted' WHERE status='Open'")

    # ── Create admin from environment variables ───────────
    if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        admin_fullname = os.environ.get("ADMIN_FULLNAME", "System Administrator")

        if not admin_password:
            print("=" * 50)
            print("  ERROR: ADMIN_PASSWORD not set!")
            print("  Create a .env file with:")
            print("  ADMIN_PASSWORD=your_secure_password")
            print("=" * 50)
            # Fallback for dev only
            admin_password = "changeme_now"
            print(f"  Using temporary password: {admin_password}")
            print("  ⚠ Change it immediately from Admin > Users")
            print("=" * 50)

        pw_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        c.execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?,?,?,?)
        """, (admin_username, pw_hash, admin_fullname, "admin"))

        print("=" * 50)
        print(f"  Admin account created!")
        print(f"  Username: {admin_username}")
        print(f"  Password: loaded from .env")
        print("=" * 50)

    conn.commit()
    conn.close()


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
