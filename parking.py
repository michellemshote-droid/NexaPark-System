import secrets
from datetime import datetime, timedelta
from database import get_connection, get_available_slot, get_or_create_vehicle
from pricing import calculate_fee, calculate_booking_payment

PLATE_MAX_LENGTH = 12
MAX_BOOKING_WINDOW = timedelta(days=7)
BOOKING_GRACE_PERIOD = timedelta(minutes=15)
PENDING_BOOKING_TIMEOUT = timedelta(minutes=15)


def normalise_plate(value):
    return " ".join(value.upper().strip().split())


def format_duration(minutes):
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def expire_stale_bookings(conn):
    """Expire old unpaid booking attempts and bookings whose window passed."""
    now = datetime.now().replace(microsecond=0)
    pending_cutoff = (now - PENDING_BOOKING_TIMEOUT).isoformat(" ")
    end_cutoff = now.isoformat(" ")

    conn.execute("""
        UPDATE bookings
        SET status='CANCELLED'
        WHERE status='PENDING_PAYMENT' AND created_at < ?
    """, (pending_cutoff,))

    conn.execute("""
        UPDATE bookings SET status='NO_SHOW'
        WHERE status='CONFIRMED' AND requested_end < ?
    """, (end_cutoff,))
    conn.commit()


def generate_booking_reference(conn):
    for _ in range(10):
        candidate = "BK-" + secrets.token_hex(3).upper()
        exists = conn.execute("SELECT 1 FROM bookings WHERE reference=?", (candidate,)).fetchone()
        if not exists:
            return candidate
    raise RuntimeError("Could not generate a unique booking reference.")


def get_active_booking_for_plate(conn, plate):
    now = datetime.now().replace(microsecond=0).isoformat(" ")
    return conn.execute("""
        SELECT b.* FROM bookings b
        JOIN vehicles v ON v.vehicle_id=b.vehicle_id
        WHERE v.plate_number=? AND b.status='CONFIRMED'
          AND b.requested_start <= ? AND b.requested_end >= ?
        ORDER BY b.requested_start ASC LIMIT 1
    """, (plate, now, now)).fetchone()


def _reserved_right_now(conn):
    now = datetime.now().replace(microsecond=0).isoformat(" ")
    return conn.execute("""
        SELECT COUNT(*) AS n FROM bookings
        WHERE status='CONFIRMED' AND requested_start <= ? AND requested_end >= ?
    """, (now, now)).fetchone()["n"]


def record_entry(plate, vehicle_type):
    plate = normalise_plate(plate)
    if not plate:
        return {"success": False, "message": "Please enter a vehicle number plate."}
    if len(plate) > PLATE_MAX_LENGTH:
        return {"success": False, "message": "Vehicle number plate is too long."}

    conn = get_connection()
    expire_stale_bookings(conn)

    active = conn.execute("""
        SELECT s.session_id FROM parking_sessions s
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        WHERE v.plate_number=? AND s.status='ACTIVE'
    """, (plate,)).fetchone()
    if active:
        conn.close()
        return {"success": False, "message": "This vehicle is already inside the parking facility."}

    booking = get_active_booking_for_plate(conn, plate)
    if not booking:
        available_count = conn.execute(
            "SELECT COUNT(*) AS n FROM parking_slots WHERE status='AVAILABLE'"
        ).fetchone()["n"]
        reserved_now = _reserved_right_now(conn)
        if available_count - reserved_now <= 0:
            conn.close()
            return {
                "success": False,
                "message": "No walk-in bays are free right now -- the remaining capacity is reserved for pre-booked vehicles. You can pre-book a bay online for a later time."
            }

    slot = get_available_slot(conn)
    if not slot:
        conn.close()
        return {"success": False, "message": "Parking is currently full."}

    vehicle = get_or_create_vehicle(conn, plate, vehicle_type)
    now = datetime.now().replace(microsecond=0)
    cur = conn.execute("""
        INSERT INTO parking_sessions(vehicle_id,slot_id,entry_time,status)
        VALUES (?,?,?,'ACTIVE')
    """, (vehicle["vehicle_id"], slot["slot_id"], now.isoformat(" ")))
    conn.execute(
        "UPDATE parking_slots SET status='OCCUPIED' WHERE slot_id=?",
        (slot["slot_id"],)
    )

    valet_requested = False
    if booking:
        conn.execute(
            "UPDATE bookings SET status='CHECKED_IN', session_id=? WHERE booking_id=?",
            (cur.lastrowid, booking["booking_id"])
        )
        valet_requested = bool(booking["valet_requested"])

    if valet_requested:
        conn.execute("""
            INSERT INTO valet_requests(session_id, drop_off_location, status)
            VALUES (?, ?, 'PARKED')
        """, (cur.lastrowid, "Pre-booked valet"))

    conn.commit()
    conn.close()

    result = {
        "success": True,
        "session_id": cur.lastrowid,
        "plate": plate,
        "vehicle_type": vehicle_type,
        "slot": slot["slot_number"],
        "entry_time": now.strftime("%d %b %Y, %I:%M %p"),
        "valet_requested": valet_requested,
    }
    if booking:
        result["booking_reference"] = booking["reference"]
    return result


def prepare_exit(plate):
    plate = normalise_plate(plate)
    conn = get_connection()
    row = conn.execute("""
        SELECT s.session_id, s.entry_time, ps.slot_number, v.plate_number,
               v.vehicle_type,
               COALESCE(vr.valet_id, NULL) AS valet_id,
               CASE WHEN vr.valet_id IS NOT NULL THEN 1 ELSE 0 END AS valet_requested,
               COALESCE(b.deposit_amount, 0) AS booking_deposit_paid,
               b.reference AS booking_reference
        FROM parking_sessions s
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        LEFT JOIN valet_requests vr ON vr.session_id=s.session_id
        LEFT JOIN bookings b ON b.session_id=s.session_id
        WHERE v.plate_number=? AND s.status='ACTIVE'
    """, (plate,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": "No active parking session was found for that plate."}

    entry_time = datetime.fromisoformat(row["entry_time"])
    exit_time = datetime.now().replace(microsecond=0)
    duration = max(0, int((exit_time - entry_time).total_seconds() // 60))
    pricing = calculate_fee(duration, valet=bool(row["valet_requested"]))
    total_price = pricing["total_price"]
    deposit_paid = int(row["booking_deposit_paid"] or 0)
    amount_due = max(0, total_price - deposit_paid)
    conn.close()

    return {
        "success": True,
        "session_id": row["session_id"],
        "plate": row["plate_number"],
        "vehicle_type": row["vehicle_type"],
        "slot": row["slot_number"],
        "entry_time": entry_time.strftime("%d %b %Y, %I:%M %p"),
        "exit_time": exit_time.strftime("%d %b %Y, %I:%M %p"),
        "duration_minutes": duration,
        "duration_text": format_duration(duration),
        "parking_fee": pricing["parking_fee"],
        "valet_fee": pricing["valet_fee"],
        "fee": total_price,
        "booking_deposit_paid": deposit_paid,
        "amount_due": amount_due,
        "booking_reference": row["booking_reference"],
    }


def complete_exit(session_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT s.*, ps.slot_number, v.plate_number,
               CASE WHEN vr.valet_id IS NOT NULL THEN 1 ELSE 0 END AS valet_requested,
               COALESCE(b.deposit_amount, 0) AS booking_deposit_paid
        FROM parking_sessions s
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        LEFT JOIN valet_requests vr ON vr.session_id=s.session_id
        LEFT JOIN bookings b ON b.session_id=s.session_id
        WHERE s.session_id=? AND s.status='ACTIVE'
    """, (session_id,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": "The parking session is no longer active."}

    entry_time = datetime.fromisoformat(row["entry_time"])
    exit_time = datetime.now().replace(microsecond=0)
    duration = max(0, int((exit_time - entry_time).total_seconds() // 60))
    pricing = calculate_fee(duration, valet=bool(row["valet_requested"]))
    total_fee = pricing["total_price"]
    deposit_paid = int(row["booking_deposit_paid"] or 0)
    amount_due = max(0, total_fee - deposit_paid)

    conn.execute("""
        UPDATE parking_sessions
        SET exit_time=?, duration_minutes=?, fee=?, status='COMPLETED'
        WHERE session_id=?
    """, (exit_time.isoformat(" "), duration, total_fee, session_id))
    conn.execute(
        "UPDATE parking_slots SET status='AVAILABLE' WHERE slot_id=?",
        (row["slot_id"],)
    )
    conn.execute("""
        INSERT INTO payments(session_id,amount,payment_time,payment_status)
        VALUES (?,?,?,'PAID')
    """, (session_id, amount_due, exit_time.isoformat(" ")))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "plate": row["plate_number"],
        "slot": row["slot_number"],
        "exit_time": exit_time.strftime("%d %b %Y, %I:%M %p"),
        "duration_text": format_duration(duration),
        "parking_fee": pricing["parking_fee"],
        "valet_fee": pricing["valet_fee"],
        "fee": total_fee,
        "booking_deposit_paid": deposit_paid,
        "amount_due": amount_due,
    }


# ---------------------------------------------------------------------------
# Online pre-booking
# ---------------------------------------------------------------------------

def create_booking(plate, vehicle_type, start_raw, end_raw, valet_requested=False):
    plate = normalise_plate(plate)
    if not plate:
        return {"success": False, "message": "Please enter a vehicle number plate."}
    if len(plate) > PLATE_MAX_LENGTH:
        return {"success": False, "message": "Vehicle number plate is too long."}
    try:
        start_dt = datetime.fromisoformat(start_raw).replace(microsecond=0)
        end_dt = datetime.fromisoformat(end_raw).replace(microsecond=0)
    except (TypeError, ValueError):
        return {"success": False, "message": "Please provide a valid arrival and departure time."}

    if end_dt <= start_dt:
        return {"success": False, "message": "The departure time must be after the arrival time."}
    if start_dt < datetime.now() - BOOKING_GRACE_PERIOD:
        return {"success": False, "message": "The arrival time can't be in the past."}
    if (end_dt - start_dt) > MAX_BOOKING_WINDOW:
        return {"success": False, "message": "Bookings can't span more than 7 days."}

    duration_minutes = max(0, int((end_dt - start_dt).total_seconds() // 60))
    pricing = calculate_fee(duration_minutes, valet=bool(valet_requested))
    payment = calculate_booking_payment(pricing["total_price"])

    # A 50% deposit of zero would create an unusable M-Pesa payment request.
    if payment["deposit_amount"] <= 0:
        return {
            "success": False,
            "message": "The selected booking duration has no parking charge, so a 50% deposit cannot be collected. Please select a longer booking window."
        }

    conn = get_connection()
    expire_stale_bookings(conn)

    total_slots = conn.execute("SELECT COUNT(*) AS n FROM parking_slots").fetchone()["n"]
    overlapping = conn.execute("""
        SELECT COUNT(*) AS n FROM bookings
        WHERE status IN ('CONFIRMED', 'PENDING_PAYMENT')
          AND requested_start < ? AND requested_end > ?
    """, (end_dt.isoformat(" "), start_dt.isoformat(" "))).fetchone()["n"]
    if overlapping >= total_slots:
        conn.close()
        return {"success": False, "message": "No bays are available for that time window. Please try a different time."}

    vehicle = get_or_create_vehicle(conn, plate, vehicle_type)
    reference = generate_booking_reference(conn)
    created_at = datetime.now().replace(microsecond=0).isoformat(" ")
    cur = conn.execute("""
        INSERT INTO bookings(
            reference, vehicle_id, requested_start, requested_end, status,
            created_at, valet_requested, parking_fee, valet_fee, total_price,
            deposit_amount, amount_paid
        )
        VALUES (?,?,?,?, 'PENDING_PAYMENT', ?, ?, ?, ?, ?, ?, 0)
    """, (
        reference, vehicle["vehicle_id"], start_dt.isoformat(" "), end_dt.isoformat(" "),
        created_at, 1 if valet_requested else 0, pricing["parking_fee"],
        pricing["valet_fee"], pricing["total_price"], payment["deposit_amount"]
    ))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "booking_id": cur.lastrowid,
        "reference": reference,
        "plate": plate,
        "vehicle_type": vehicle_type,
        "requested_start": start_dt.strftime("%d %b %Y, %I:%M %p"),
        "requested_end": end_dt.strftime("%d %b %Y, %I:%M %p"),
        "duration_minutes": duration_minutes,
        "duration_text": format_duration(duration_minutes),
        "parking_fee": pricing["parking_fee"],
        "valet_fee": pricing["valet_fee"],
        "total_price": payment["total_price"],
        "deposit_amount": payment["deposit_amount"],
        "balance_amount": payment["balance_amount"],
        "valet_requested": bool(valet_requested),
    }


def confirm_booking_payment(booking_id, amount):
    conn = get_connection()
    row = conn.execute("SELECT * FROM bookings WHERE booking_id=?", (booking_id,)).fetchone()
    if not row:
        conn.close()
        return False, "Booking not found."
    if row["status"] != "PENDING_PAYMENT":
        conn.close()
        return row["status"] == "CONFIRMED", "Booking is already processed."
    if int(amount) != int(row["deposit_amount"]):
        conn.close()
        return False, "The M-Pesa amount does not match the required booking deposit."

    conn.execute("""
        UPDATE bookings
        SET status='CONFIRMED', amount_paid=?
        WHERE booking_id=?
    """, (int(amount), booking_id))
    conn.commit()
    conn.close()
    return True, "Booking confirmed."


def cancel_booking(reference, plate):
    plate = normalise_plate(plate)
    reference = (reference or "").strip().upper()
    conn = get_connection()
    row = conn.execute("""
        SELECT b.* FROM bookings b
        JOIN vehicles v ON v.vehicle_id=b.vehicle_id
        WHERE b.reference=? AND v.plate_number=?
    """, (reference, plate)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": "No matching booking was found for that reference and plate."}
    if row["status"] not in ("CONFIRMED", "PENDING_PAYMENT"):
        conn.close()
        status_label = row["status"].replace("_", " ").title()
        return {"success": False, "message": f"This booking is already {status_label} and can't be cancelled."}
    conn.execute("UPDATE bookings SET status='CANCELLED' WHERE booking_id=?", (row["booking_id"],))
    conn.commit()
    conn.close()
    return {"success": True, "reference": row["reference"]}


# ---------------------------------------------------------------------------
# Valet operations
# ---------------------------------------------------------------------------

def record_valet_dropoff(plate, vehicle_type, drop_off_location):
    result = record_entry(plate, vehicle_type)
    if not result["success"]:
        return result
    conn = get_connection()
    existing = conn.execute(
        "SELECT valet_id FROM valet_requests WHERE session_id=?", (result["session_id"],)
    ).fetchone()
    if not existing:
        conn.execute("""
            INSERT INTO valet_requests(session_id, drop_off_location, status)
            VALUES (?,?,'PARKED')
        """, (result["session_id"], (drop_off_location or "").strip()[:200]))
        conn.commit()
    conn.close()
    result["drop_off_location"] = (drop_off_location or "").strip()
    result["valet_requested"] = True
    return result


def request_valet_pickup(plate):
    plate = normalise_plate(plate)
    conn = get_connection()
    row = conn.execute("""
        SELECT vr.* FROM valet_requests vr
        JOIN parking_sessions s ON s.session_id=vr.session_id
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        WHERE v.plate_number=? AND s.status='ACTIVE' AND vr.status IN ('PARKED','RETRIEVING')
    """, (plate,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": "No active valet-parked vehicle was found for that plate."}
    now = datetime.now().replace(microsecond=0).isoformat(" ")
    conn.execute("""
        UPDATE valet_requests SET status='RETRIEVING', pickup_requested_at=?
        WHERE valet_id=?
    """, (now, row["valet_id"]))
    conn.commit()
    conn.close()
    return {"success": True, "plate": plate}


def mark_valet_retrieving(valet_id):
    conn = get_connection()
    now = datetime.now().replace(microsecond=0).isoformat(" ")
    conn.execute("""
        UPDATE valet_requests SET status='RETRIEVING',
               pickup_requested_at=COALESCE(pickup_requested_at, ?)
        WHERE valet_id=? AND status='PARKED'
    """, (now, valet_id))
    conn.commit()
    conn.close()


def mark_valet_delivered(valet_id):
    conn = get_connection()
    now = datetime.now().replace(microsecond=0).isoformat(" ")
    conn.execute("""
        UPDATE valet_requests SET status='DELIVERED', pickup_completed_at=?
        WHERE valet_id=? AND status='RETRIEVING'
    """, (now, valet_id))
    conn.commit()
    conn.close()
