from mpesa import initiate_stk_push
import os
import getpass
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from parking import (
    record_entry, prepare_exit, complete_exit,
    create_booking, confirm_booking_payment, cancel_booking,
    record_valet_dropoff, request_valet_pickup,
    mark_valet_retrieving, mark_valet_delivered
)
from database import (
    init_db, get_dashboard_stats, get_active_vehicles, get_slots, get_payments,
    get_history, get_report, get_bookings, get_valet_requests, create_mpesa_transaction,
    get_mpesa_transaction_by_checkout_id,
    update_mpesa_transaction,
    admin_count, username_exists, create_admin_account
)
from auth import authenticate_admin, ensure_default_admin, validate_password_strength

app = Flask(__name__)
MPESA_CALLBACK_URL = os.getenv(
    "MPESA_CALLBACK_URL",
    "https://your-public-callback-url.example.com/mpesa/callback"
)
app.config["SECRET_KEY"] = os.environ.get("NEXAPARK_SECRET_KEY", "nexapark-local-development-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("NEXAPARK_HTTPS", "0") == "1"

init_db()
ensure_default_admin()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please sign in as an admin to continue.", "error")
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.get("/")
def home():
    return render_template("index.html", slots=get_slots())

@app.get("/entry")
@app.get("/entry/")
def entry_page():
    return render_template("entry.html")

@app.post("/entry")
@app.post("/entry/")
def entry():
    plate = request.form.get("plate", "")
    vehicle_type = request.form.get("vehicle_type", "Car")
    result = record_entry(plate, vehicle_type)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("entry_page"))
    return render_template("entry_success.html", result=result)

@app.get("/exit")
@app.get("/exit/")
def exit_page():
    return render_template("exit.html")

@app.post("/exit")
@app.post("/exit/")
def exit_vehicle():
    plate = request.form.get("plate", "")
    result = prepare_exit(plate)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("exit_page"))
    session["pending_exit"] = result["session_id"]
    session["pending_plate"] = result["plate"]
    return render_template("payment.html", result=result)

@app.post("/pay")
def pay():
    session_id = session.get("pending_exit")
    if not session_id:
        flash("No pending parking session was found. Please start the exit process again.", "error")
        return redirect(url_for("exit_page"))

    phone_number = request.form.get("phone_number", "").strip()
    if not phone_number:
        flash("Please enter your M-Pesa phone number.", "error")
        return redirect(url_for("exit_page"))

    try:
        pending_plate = session.get("pending_plate")
        exit_result = prepare_exit(pending_plate or "")
        if not exit_result["success"]:
            flash(exit_result["message"], "error")
            return redirect(url_for("exit_page"))

        amount = int(exit_result["amount_due"])
        if amount <= 0:
            result = complete_exit(session_id)
            if not result["success"]:
                flash(result["message"], "error")
                return redirect(url_for("exit_page"))
            session.pop("pending_exit", None)
            session.pop("pending_plate", None)
            return render_template("exit_success.html", result=result)

        account_reference = f"NEXA-EXIT-{session_id}-{uuid.uuid4().hex[:8].upper()}"
        mpesa_result = initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=account_reference,
            transaction_description="NexaPark parking balance",
            callback_url=MPESA_CALLBACK_URL
        )
        checkout_id = mpesa_result.get("CheckoutRequestID")
        if not checkout_id:
            raise RuntimeError("M-Pesa did not return a CheckoutRequestID.")

        create_mpesa_transaction(
            session_id=session_id,
            checkout_request_id=checkout_id,
            merchant_request_id=mpesa_result.get("MerchantRequestID"),
            phone_number=phone_number,
            amount=amount,
            account_reference=account_reference,
            payment_type="EXIT_BALANCE",
        )

        session["pending_phone"] = phone_number
        return render_template(
            "payment_pending.html",
            result=exit_result,
            mpesa_response=mpesa_result,
            payment_type="exit",
        )
    except Exception as exc:
        flash(f"Could not start the M-Pesa payment: {exc}", "error")
        return redirect(url_for("exit_page"))

@app.get("/payment/status/<checkout_request_id>")
def payment_status(checkout_request_id):
    transaction = get_mpesa_transaction_by_checkout_id(checkout_request_id)
    if not transaction:
        return jsonify({"status": "UNKNOWN"}), 404
    return jsonify({"status": transaction["status"]})

@app.get("/payment/exit/<checkout_request_id>")
def exit_status_page(checkout_request_id):
    transaction = get_mpesa_transaction_by_checkout_id(checkout_request_id)
    if not transaction or transaction["payment_type"] != "EXIT_BALANCE" or transaction["status"] != "PAID":
        return redirect(url_for("exit_page"))
    conn = __import__("database").get_connection()
    row = conn.execute("""
        SELECT s.exit_time, s.duration_minutes, s.fee, v.plate_number,
               ps.slot_number, COALESCE(b.deposit_amount,0) AS deposit_paid,
               CASE WHEN vr.valet_id IS NOT NULL THEN 1 ELSE 0 END AS valet_requested
        FROM parking_sessions s
        JOIN vehicles v ON v.vehicle_id=s.vehicle_id
        JOIN parking_slots ps ON ps.slot_id=s.slot_id
        LEFT JOIN bookings b ON b.session_id=s.session_id
        LEFT JOIN valet_requests vr ON vr.session_id=s.session_id
        WHERE s.session_id=? AND s.status='COMPLETED'
    """, (transaction["session_id"],)).fetchone()
    conn.close()
    if not row:
        return redirect(url_for("home"))
    from pricing import calculate_fee
    pricing = calculate_fee(row["duration_minutes"], bool(row["valet_requested"]))
    result = {
        "plate": row["plate_number"], "slot": row["slot_number"],
        "duration_text": __import__("parking").format_duration(row["duration_minutes"]),
        "parking_fee": pricing["parking_fee"], "valet_fee": pricing["valet_fee"],
        "fee": row["fee"], "booking_deposit_paid": row["deposit_paid"],
        "amount_due": transaction["amount"],
    }
    return render_template("exit_success.html", result=result)

@app.post("/mpesa/callback")
def mpesa_callback():
    data = request.get_json(silent=True) or {}
    stk_callback = data.get("Body", {}).get("stkCallback", {})
    result_code = stk_callback.get("ResultCode")
    checkout_request_id = stk_callback.get("CheckoutRequestID")

    if not checkout_request_id:
        return {"ResultCode": 0, "ResultDesc": "Callback received"}

    transaction = get_mpesa_transaction_by_checkout_id(checkout_request_id)
    if not transaction:
        return {"ResultCode": 0, "ResultDesc": "Unknown payment reference"}

    if result_code != 0:
        description = stk_callback.get("ResultDesc") or "M-Pesa payment was not completed."
        status = "CANCELLED" if result_code == 1032 else "FAILED"
        update_mpesa_transaction(checkout_request_id, status, result_code, description)
        return {"ResultCode": 0, "ResultDesc": "Callback received"}

    metadata = {
        item.get("Name"): item.get("Value")
        for item in stk_callback.get("CallbackMetadata", {}).get("Item", [])
        if item.get("Name")
    }
    receipt = metadata.get("MpesaReceiptNumber")
    paid_amount = int(metadata.get("Amount") or transaction["amount"])

    expected_amount = int(transaction["amount"])
    if paid_amount != expected_amount:
        update_mpesa_transaction(
            checkout_request_id, "FAILED", result_code,
            f"Paid amount KSh {paid_amount} did not match the expected KSh {expected_amount}.", receipt
        )
        return {"ResultCode": 0, "ResultDesc": "Callback received"}

    update_mpesa_transaction(
        checkout_request_id,
        "PAID",
        result_code,
        stk_callback.get("ResultDesc"),
        receipt,
    )

    if transaction["payment_type"] == "BOOKING_DEPOSIT":
        confirm_booking_payment(transaction["booking_id"], paid_amount)
    elif transaction["payment_type"] == "EXIT_BALANCE":
        complete_exit(transaction["session_id"])

    return {"ResultCode": 0, "ResultDesc": "Callback received successfully"}

@app.get("/api/slots")
def api_slots():
    return jsonify(get_slots())

# ---------------------------------------------------------------------------
# Online pre-booking
# ---------------------------------------------------------------------------

@app.get("/book")
@app.get("/book/")
def book_page():
    return render_template("book.html")

@app.post("/book")
@app.post("/book/")
def book():
    plate = request.form.get("plate", "")
    vehicle_type = request.form.get("vehicle_type", "Car")
    start = request.form.get("start", "")
    end = request.form.get("end", "")
    phone_number = request.form.get("phone_number", "").strip()
    valet_requested = request.form.get("valet_requested") == "yes"

    if not phone_number:
        flash("Please enter the M-Pesa phone number for the booking deposit.", "error")
        return redirect(url_for("book_page"))

    result = create_booking(plate, vehicle_type, start, end, valet_requested)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("book_page"))

    try:
        account_reference = f"NEXA-BOOK-{result['reference']}"
        mpesa_result = initiate_stk_push(
            phone_number=phone_number,
            amount=result["deposit_amount"],
            account_reference=account_reference,
            transaction_description="NexaPark booking deposit",
            callback_url=MPESA_CALLBACK_URL
        )
        checkout_id = mpesa_result.get("CheckoutRequestID")
        if not checkout_id:
            raise RuntimeError("M-Pesa did not return a CheckoutRequestID.")

        create_mpesa_transaction(
            session_id=None,
            booking_id=result["booking_id"],
            checkout_request_id=checkout_id,
            merchant_request_id=mpesa_result.get("MerchantRequestID"),
            phone_number=phone_number,
            amount=result["deposit_amount"],
            account_reference=account_reference,
            payment_type="BOOKING_DEPOSIT",
        )
        return render_template(
            "book_payment_pending.html",
            result=result,
            mpesa_response=mpesa_result,
            phone_number=phone_number,
        )
    except Exception as exc:
        cancel_booking(result["reference"], result["plate"])
        flash(f"Could not start the booking deposit payment: {exc}", "error")
        return redirect(url_for("book_page"))

@app.get("/book/status/<checkout_request_id>")
def booking_payment_status(checkout_request_id):
    transaction = get_mpesa_transaction_by_checkout_id(checkout_request_id)
    if not transaction or transaction["payment_type"] != "BOOKING_DEPOSIT":
        return jsonify({"status": "UNKNOWN"}), 404
    return jsonify({"status": transaction["status"]})

@app.get("/book/success/<reference>")
def book_success_page(reference):
    from database import get_booking_by_reference
    result = get_booking_by_reference(reference)
    if not result:
        flash("Booking could not be found.", "error")
        return redirect(url_for("book_page"))
    return render_template("book_success.html", result=result)

@app.get("/book/cancel")
@app.get("/book/cancel/")
def book_cancel_page():
    return render_template("book_cancel.html")

@app.post("/book/cancel")
@app.post("/book/cancel/")
def book_cancel():
    reference = request.form.get("reference", "")
    plate = request.form.get("plate", "")
    result = cancel_booking(reference, plate)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("book_cancel_page"))
    flash(f"Booking {result['reference']} has been cancelled.", "success")
    return redirect(url_for("home"))

# ---------------------------------------------------------------------------
# Valet operations
# ---------------------------------------------------------------------------

@app.get("/valet/dropoff")
@app.get("/valet/dropoff/")
def valet_dropoff_page():
    return render_template("valet_dropoff.html")

@app.post("/valet/dropoff")
@app.post("/valet/dropoff/")
def valet_dropoff():
    plate = request.form.get("plate", "")
    vehicle_type = request.form.get("vehicle_type", "Car")
    drop_off_location = request.form.get("drop_off_location", "")
    result = record_valet_dropoff(plate, vehicle_type, drop_off_location)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("valet_dropoff_page"))
    return render_template("valet_dropoff_success.html", result=result)

@app.get("/valet/pickup")
@app.get("/valet/pickup/")
def valet_pickup_page():
    return render_template("valet_pickup.html")

@app.post("/valet/pickup")
@app.post("/valet/pickup/")
def valet_pickup():
    plate = request.form.get("plate", "")
    result = request_valet_pickup(plate)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("valet_pickup_page"))
    flash("Your pickup request has been sent to the valet team. They'll bring your car around shortly.", "success")
    return redirect(url_for("home"))

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.get("/admin/login")
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard_page"))
    if admin_count() == 0:
        flash("No admin account exists yet. Run 'flask create-admin' from the project folder to create one.", "error")
    return render_template("admin/login.html")

@app.post("/admin/login")
def admin_login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    result = authenticate_admin(username, password)
    if not result["success"]:
        flash(result["message"], "error")
        return redirect(url_for("admin_login"))
    session.clear()
    session["admin_id"] = result["admin_id"]
    session["admin_username"] = result["username"]
    next_url = request.args.get("next") or request.form.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("admin_dashboard_page"))

@app.post("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    return redirect(url_for("admin_dashboard_page"))

@app.get("/admin/dashboard")
@admin_required
def admin_dashboard_page():
    return render_template("admin/dashboard.html", stats=get_dashboard_stats(), slots=get_slots())

@app.get("/admin/vehicles")
@admin_required
def admin_vehicles():
    return render_template("admin/vehicles.html", vehicles=get_active_vehicles())

@app.get("/admin/slots")
@admin_required
def admin_slots():
    return render_template("admin/slots.html", slots=get_slots())

@app.get("/admin/bookings")
@admin_required
def admin_bookings():
    return render_template("admin/bookings.html", bookings=get_bookings())

@app.get("/admin/valet")
@admin_required
def admin_valet():
    return render_template("admin/valet.html", valet_requests=get_valet_requests())

@app.post("/admin/valet/<int:valet_id>/retrieve")
@admin_required
def admin_valet_retrieve(valet_id):
    mark_valet_retrieving(valet_id)
    flash("Marked as retrieving.", "success")
    return redirect(url_for("admin_valet"))

@app.post("/admin/valet/<int:valet_id>/deliver")
@admin_required
def admin_valet_deliver(valet_id):
    mark_valet_delivered(valet_id)
    flash("Marked as delivered.", "success")
    return redirect(url_for("admin_valet"))

@app.get("/admin/payments")
@admin_required
def admin_payments():
    return render_template("admin/payments.html", payments=get_payments())

@app.get("/admin/history")
@admin_required
def admin_history():
    return render_template("admin/history.html", history=get_history())

@app.get("/admin/reports")
@admin_required
def admin_reports():
    return render_template("admin/reports.html", report=get_report())

# ---------------------------------------------------------------------------
# CLI: interactive, non-hardcoded admin account creation
# ---------------------------------------------------------------------------

@app.cli.command("create-admin")
def create_admin_cli():
    """Interactively create an admin account.

    The password is entered with getpass (never echoed to the screen,
    never written to shell history, never printed or logged by the app)
    and is stored only as a salted hash. This replaces the old behaviour
    of auto-generating a password and printing it to the console on first
    run, which could end up captured in terminal scrollback, screen
    recordings, or log files.
    """
    username = input("New admin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return
    if username_exists(username):
        print(f"An admin account named '{username}' already exists.")
        return
    password = getpass.getpass("New admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match. Nothing was created.")
        return
    ok, message = validate_password_strength(password)
    if not ok:
        print(message)
        return
    create_admin_account(username, password)
    print(f"Admin account '{username}' created.")

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
