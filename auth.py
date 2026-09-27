from werkzeug.security import check_password_hash
from database import (
    get_connection, get_admin_by_username, is_locked_out,
    register_failed_login, register_successful_login, LOCKOUT_MINUTES
)

def authenticate_admin(username, password):
    """Check admin credentials with basic brute-force protection.

    Returns {"success": True, "admin_id": ..., "username": ...} on success,
    or {"success": False, "message": ...} on failure -- including when the
    account is temporarily locked out from repeated failed attempts.
    """
    conn = get_connection()
    admin = get_admin_by_username(conn, username)
    if not admin:
        conn.close()
        return {"success": False, "message": "Invalid username or password."}
    if is_locked_out(admin):
        conn.close()
        return {
            "success": False,
            "message": f"This account is temporarily locked after too many failed sign-in attempts. Try again in about {LOCKOUT_MINUTES} minutes."
        }
    if not check_password_hash(admin["password_hash"], password):
        register_failed_login(conn, admin)
        conn.close()
        return {"success": False, "message": "Invalid username or password."}
    register_successful_login(conn, admin)
    conn.close()
    return {"success": True, "admin_id": admin["admin_id"], "username": admin["username"]}

def validate_password_strength(password):
    """Minimal strength check used when an admin account is created."""
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."
    if not any(c.isdigit() for c in password):
        return False, "Password must include at least one digit."
    if not any(c.isalpha() for c in password):
        return False, "Password must include at least one letter."
    return True, ""

def ensure_default_admin():
    from database import ensure_default_admin as seed
    seed()
