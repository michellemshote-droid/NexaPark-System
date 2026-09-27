import os
import sqlite3
import secrets
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "parking.db")

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _ensure_admin_columns(conn):
    """Add columns introduced after the admins table already existed.

    SQLite's CREATE TABLE IF NOT EXISTS won't retrofit columns onto a table
    that's already there, so a lightweight, idempotent ALTER TABLE step
    keeps existing databases (and existing admin accounts) working without
    any manual migration step.
    """
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(admins)").fetchall()}
    if "failed_attempts" not in cols:
        conn.execute("ALTER TABLE admins ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0")
    if "locked_until" not in cols:
        conn.execute("ALTER TABLE admins ADD COLUMN locked_until TEXT")
    conn.commit()

def _migrate_payment_and_booking_schema(conn):
    """Upgrade databases created by earlier NexaPark versions."""
    booking_cols = {row["name"] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()}
    if booking_cols and "PENDING_PAYMENT" not in str(conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'"
    ).fetchone()["sql"]):
        conn.execute("ALTER TABLE bookings RENAME TO bookings_old")
        conn.execute("""
            CREATE TABLE bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                vehicle_id INTEGER NOT NULL,
                session_id INTEGER,
                requested_start TEXT NOT NULL,
                requested_end TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING_PAYMENT','CONFIRMED','CHECKED_IN','CANCELLED','NO_SHOW')),
                created_at TEXT NOT NULL,
                valet_requested INTEGER NOT NULL DEFAULT 0,
                parking_fee INTEGER NOT NULL DEFAULT 0,
                valet_fee INTEGER NOT NULL DEFAULT 0,
                total_price INTEGER NOT NULL DEFAULT 0,
                deposit_amount INTEGER NOT NULL DEFAULT 0,
                amount_paid INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(vehicle_id) REFERENCES vehicles(vehicle_id),
                FOREIGN KEY(session_id) REFERENCES parking_sessions(session_id)
            )
        """)
        conn.execute("""
            INSERT INTO bookings(booking_id,reference,vehicle_id,session_id,requested_start,requested_end,status,created_at)
            SELECT booking_id,reference,vehicle_id,session_id,requested_start,requested_end,status,created_at
            FROM bookings_old
        """)
        conn.execute("DROP TABLE bookings_old")

    mpesa_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='mpesa_transactions'"
    ).fetchone()
    if mpesa_sql and "booking_id INTEGER" not in mpesa_sql["sql"]:
        conn.execute("ALTER TABLE mpesa_transactions RENAME TO mpesa_transactions_old")
        conn.execute("""
            CREATE TABLE mpesa_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                booking_id INTEGER,
                payment_type TEXT NOT NULL DEFAULT 'EXIT' CHECK(payment_type IN ('BOOKING_DEPOSIT','EXIT_BALANCE')),
                checkout_request_id TEXT UNIQUE NOT NULL,
                merchant_request_id TEXT,
                phone_number TEXT NOT NULL,
                amount INTEGER NOT NULL,
                account_reference TEXT,
                status TEXT NOT NULL CHECK(status IN ('PENDING','PAID','FAILED','CANCELLED')),
                mpesa_receipt_number TEXT,
                result_code INTEGER,
                result_description TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(session_id) REFERENCES parking_sessions(session_id),
                FOREIGN KEY(booking_id) REFERENCES bookings(booking_id)
            )
        """)
        conn.execute("""
            INSERT INTO mpesa_transactions(
                transaction_id,session_id,checkout_request_id,merchant_request_id,phone_number,amount,
                account_reference,status,mpesa_receipt_number,result_code,result_description,created_at,completed_at,
                payment_type
            )
            SELECT transaction_id,session_id,checkout_request_id,merchant_request_id,phone_number,amount,
                   account_reference,status,mpesa_receipt_number,result_code,result_description,created_at,completed_at,'EXIT'
            FROM mpesa_transactions_old
        """)
        conn.execute("DROP TABLE mpesa_transactions_old")
    conn.commit()

def init_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS vehicles (
        vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT UNIQUE NOT NULL,
        vehicle_type TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS parking_slots (
        slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_number TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('AVAILABLE','OCCUPIED'))
    );

    CREATE TABLE IF NOT EXISTS parking_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL,
        slot_id INTEGER NOT NULL,
        entry_time TEXT NOT NULL,
        exit_time TEXT,
        duration_minutes INTEGER,
        fee INTEGER,
        status TEXT NOT NULL CHECK(status IN ('ACTIVE','COMPLETED')),
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(vehicle_id),
        FOREIGN KEY(slot_id) REFERENCES parking_slots(slot_id)
    );

    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER UNIQUE NOT NULL,
        amount INTEGER NOT NULL,
        payment_time TEXT NOT NULL,
        payment_status TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES parking_sessions(session_id)
    );

        CREATE TABLE IF NOT EXISTS mpesa_transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        booking_id INTEGER,
        payment_type TEXT NOT NULL DEFAULT 'EXIT',
        checkout_request_id TEXT UNIQUE NOT NULL,
        merchant_request_id TEXT,
        phone_number TEXT NOT NULL,
        amount INTEGER NOT NULL,
        account_reference TEXT,
        status TEXT NOT NULL CHECK(
            status IN ('PENDING', 'PAID', 'FAILED', 'CANCELLED')
        ),
        mpesa_receipt_number TEXT,
        result_code INTEGER,
        result_description TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(session_id) REFERENCES parking_sessions(session_id),
        FOREIGN KEY(booking_id) REFERENCES bookings(booking_id)
    );

    CREATE TABLE IF NOT EXISTS bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE NOT NULL,
        vehicle_id INTEGER NOT NULL,
        session_id INTEGER,
        requested_start TEXT NOT NULL,
        requested_end TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PENDING_PAYMENT','CONFIRMED','CHECKED_IN','CANCELLED','NO_SHOW')),
        created_at TEXT NOT NULL,
        valet_requested INTEGER NOT NULL DEFAULT 0,
        parking_fee INTEGER NOT NULL DEFAULT 0,
        valet_fee INTEGER NOT NULL DEFAULT 0,
        total_price INTEGER NOT NULL DEFAULT 0,
        deposit_amount INTEGER NOT NULL DEFAULT 0,
        amount_paid INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(vehicle_id),
        FOREIGN KEY(session_id) REFERENCES parking_sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS valet_requests (
        valet_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER UNIQUE NOT NULL,
        drop_off_location TEXT,
        pickup_requested_at TEXT,
        pickup_completed_at TEXT,
        status TEXT NOT NULL CHECK(status IN ('PARKED','RETRIEVING','DELIVERED')),
        FOREIGN KEY(session_id) REFERENCES parking_sessions(session_id)
    );
    """)
    _migrate_payment_and_booking_schema(conn)
    _ensure_admin_columns(conn)
    count = conn.execute("SELECT COUNT(*) AS n FROM parking_slots").fetchone()["n"]
    if count == 0:
        for i in range(1, 21):
            letter = chr(64 + ((i - 1) // 10) + 1)
            number = ((i - 1) % 10) + 1
            conn.execute(
                "INSERT INTO parking_slots(slot_number,status) VALUES (?, 'AVAILABLE')",
                (f"{letter}{number:02d}",)
            )
    conn.commit()
    conn.close()

def ensure_default_admin():
    """Optionally seed an admin account from environment variables.

    This never invents a password or prints one anywhere. If both
    NEXAPARK_ADMIN_USERNAME and NEXAPARK_ADMIN_PASSWORD are set (useful for
    scripted/first deploys where the deployer supplies their own secret),
    an account is created once. Otherwise nothing happens here at all --
    use the `flask create-admin` CLI command to set up the first account
    interactively instead. Existing accounts are never overwritten, so
    changing these variables later won't silently change a live password.
    """
    username = os.environ.get("NEXAPARK_ADMIN_USERNAME", "").strip()
    password = os.environ.get("NEXAPARK_ADMIN_PASSWORD", "").strip()
    if not username or not password:
        return
    conn = get_connection()
    try:
        row = conn.execute("SELECT admin_id FROM admins WHERE username=?", (username,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO admins(username,password_hash) VALUES (?,?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
    finally:
        conn.close()

def admin_count():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) AS n FROM admins").fetchone()["n"]
    conn.close()
    return n

def username_exists(username):
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone()
    conn.close()
    return row is not None

def create_admin_account(username, password):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO admins(username,password_hash) VALUES (?,?)",
            (username, generate_password_hash(password))
        )
        conn.commit()
    finally:
        conn.close()

def get_admin_by_username(conn, username):
    return conn.execute(
        "SELECT * FROM admins WHERE username=?", (username,)
    ).fetchone()

def is_locked_out(admin_row):
    if not admin_row["locked_until"]:
        return False
    return datetime.fromisoformat(admin_row["locked_until"]) > datetime.now()

def register_failed_login(conn, admin_row):
    attempts = admin_row["failed_attempts"] + 1
    locked_until = admin_row["locked_until"]
    if attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        locked_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(" ")
        attempts = 0
    conn.execute(
        "UPDATE admins SET failed_attempts=?, locked_until=? WHERE admin_id=?",
        (attempts, locked_until, admin_row["admin_id"])
    )
    conn.commit()

def register_successful_login(conn, admin_row):
    conn.execute(
        "UPDATE admins SET failed_attempts=0, locked_until=NULL WHERE admin_id=?",
        (admin_row["admin_id"],)
    )
    conn.commit()

def get_available_slot(conn):
    return conn.execute(
        "SELECT * FROM parking_slots WHERE status='AVAILABLE' ORDER BY slot_id LIMIT 1"
    ).fetchone()

def get_or_create_vehicle(conn, plate, vehicle_type):
    row = conn.execute(
        "SELECT * FROM vehicles WHERE plate_number=?", (plate,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE vehicles SET vehicle_type=? WHERE vehicle_id=?",
            (vehicle_type, row["vehicle_id"])
        )
        return conn.execute(
            "SELECT * FROM vehicles WHERE vehicle_id=?", (row["vehicle_id"],)
        ).fetchone()
    cur = conn.execute(
        "INSERT INTO vehicles(plate_number,vehicle_type) VALUES (?,?)",
        (plate, vehicle_type)
    )
    return conn.execute(
        "SELECT * FROM vehicles WHERE vehicle_id=?", (cur.lastrowid,)
    ).fetchone()

def get_slots():
    conn = get_connection()
    rows = conn.execute("""
        SELECT ps.*,
               v.plate_number,
               v.vehicle_type,
               s.entry_time
        FROM parking_slots ps
        LEFT JOIN parking_sessions s
          ON s.slot_id=ps.slot_id AND s.status='ACTIVE'
        LEFT JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        ORDER BY ps.slot_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_dashboard_stats():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) AS n FROM parking_slots").fetchone()["n"]
    available = conn.execute("SELECT COUNT(*) AS n FROM parking_slots WHERE status='AVAILABLE'").fetchone()["n"]
    occupied = total - available
    inside = conn.execute("SELECT COUNT(*) AS n FROM parking_sessions WHERE status='ACTIVE'").fetchone()["n"]
    today_revenue = conn.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM payments
        WHERE payment_status='PAID' AND date(payment_time)=date('now','localtime')
    """).fetchone()["total"]
    entered_today = conn.execute("""
        SELECT COUNT(*) AS n FROM parking_sessions
        WHERE date(entry_time)=date('now','localtime')
    """).fetchone()["n"]
    exited_today = conn.execute("""
        SELECT COUNT(*) AS n FROM parking_sessions
        WHERE status='COMPLETED' AND date(exit_time)=date('now','localtime')
    """).fetchone()["n"]
    conn.close()
    return {
        "total": total, "available": available, "occupied": occupied,
        "inside": inside, "today_revenue": today_revenue,
        "entered_today": entered_today, "exited_today": exited_today
    }

def get_active_vehicles():
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.plate_number, v.vehicle_type, ps.slot_number,
               s.entry_time
        FROM parking_sessions s
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        WHERE s.status='ACTIVE'
        ORDER BY s.entry_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_payments():
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.plate_number, ps.slot_number, s.duration_minutes,
               p.amount, p.payment_time, p.payment_status
        FROM payments p
        JOIN parking_sessions s ON s.session_id=p.session_id
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        ORDER BY p.payment_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_history():
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.plate_number, v.vehicle_type, ps.slot_number,
               s.entry_time, s.exit_time, s.duration_minutes,
               s.fee, s.status
        FROM parking_sessions s
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        ORDER BY s.entry_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_report():
    conn = get_connection()
    report = conn.execute("""
        SELECT
            COUNT(*) AS total_sessions,
            SUM(CASE WHEN status='ACTIVE' THEN 1 ELSE 0 END) AS active_sessions,
            SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) AS completed_sessions,
            COALESCE(SUM(CASE WHEN status='COMPLETED' THEN fee ELSE 0 END),0) AS revenue,
            SUM(CASE WHEN status='COMPLETED' AND fee=0 THEN 1 ELSE 0 END) AS free_visits,
            SUM(CASE WHEN status='COMPLETED' AND fee>0 THEN 1 ELSE 0 END) AS paid_visits
        FROM parking_sessions
        WHERE date(entry_time)=date('now','localtime')
    """).fetchone()
    conn.close()
    return dict(report)

def get_bookings():
    conn = get_connection()
    rows = conn.execute("""
        SELECT b.reference, b.status, b.requested_start, b.requested_end,
               b.created_at, v.plate_number, v.vehicle_type, b.valet_requested,
               b.parking_fee, b.valet_fee, b.total_price, b.deposit_amount, b.amount_paid
        FROM bookings b
        JOIN vehicles v ON v.vehicle_id=b.vehicle_id
        ORDER BY b.requested_start DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_valet_requests():
    conn = get_connection()
    rows = conn.execute("""
        SELECT vr.valet_id, vr.drop_off_location, vr.status,
               vr.pickup_requested_at, vr.pickup_completed_at,
               v.plate_number, v.vehicle_type, ps.slot_number,
               s.entry_time, s.status AS session_status
        FROM valet_requests vr
        JOIN parking_sessions s ON s.session_id=vr.session_id
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        ORDER BY
            CASE vr.status WHEN 'PARKED' THEN 0 WHEN 'RETRIEVING' THEN 1 ELSE 2 END,
            s.entry_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_mpesa_transaction(
    session_id,
    checkout_request_id,
    merchant_request_id,
    phone_number,
    amount,
    account_reference,
    booking_id=None,
    payment_type="EXIT_BALANCE",
):
    conn = get_connection()
    created_at = datetime.now().replace(microsecond=0).isoformat(" ")
    conn.execute("""
        INSERT INTO mpesa_transactions(
            session_id, booking_id, payment_type, checkout_request_id, merchant_request_id,
            phone_number, amount, account_reference, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
    """, (
        session_id, booking_id, payment_type, checkout_request_id, merchant_request_id,
        phone_number, amount, account_reference, created_at
    ))
    conn.commit()
    conn.close()


def get_mpesa_transaction_by_checkout_id(checkout_request_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM mpesa_transactions WHERE checkout_request_id=?", (checkout_request_id,)).fetchone()
    conn.close()
    return row

def update_mpesa_transaction(
    checkout_request_id,
    status,
    result_code=None,
    result_description=None,
    mpesa_receipt_number=None
):
    conn = get_connection()
    completed_at = None
    if status in ("PAID", "FAILED", "CANCELLED"):
        completed_at = datetime.now().replace(microsecond=0).isoformat(" ")
    conn.execute("""
        UPDATE mpesa_transactions
        SET status=?, result_code=?, result_description=?, mpesa_receipt_number=?, completed_at=?
        WHERE checkout_request_id=?
    """, (status, result_code, result_description, mpesa_receipt_number, completed_at, checkout_request_id))
    conn.commit()
    conn.close()


def get_booking_by_reference(reference):
    conn = get_connection()
    row = conn.execute("""
        SELECT b.reference, b.status, b.requested_start, b.requested_end,
               b.created_at, v.plate_number, v.vehicle_type, b.valet_requested,
               b.parking_fee, b.valet_fee, b.total_price, b.deposit_amount, b.amount_paid
        FROM bookings b
        JOIN vehicles v ON v.vehicle_id=b.vehicle_id
        WHERE b.reference=?
    """, (reference.strip().upper(),)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)
