from functools import wraps
from flask import session, redirect, url_for, flash, abort


# ── Role hierarchy ────────────────────────────────────────
ROLE_PERMISSIONS = {
    "admin": {
        "can_manage_users", "can_manage_vendors", "can_manage_materials",
        "can_manage_products", "can_create_pr", "can_approve_pr",
        "can_generate_rfq", "can_view_all"
    },
    "purchasing": {
        "can_manage_vendors", "can_generate_rfq",
        "can_create_pr", "can_view_all"
    },
    "planning": {
        "can_create_pr", "can_view_all"
    },
    "viewer": {
        "can_view_all"
    },
}

ROLE_LABELS = {
    "admin":     "Administrator",
    "purchasing": "Purchasing Officer",
    "planning":  "Planning Officer",
    "viewer":    "Viewer",
}

# PR status flow — من يقدر يغير لأيا حالة
PR_STATUS_FLOW = {
    "Draft":     {"next": "Submitted",  "roles": ["planning", "purchasing", "admin"]},
    "Submitted": {"next": "Approved",   "roles": ["purchasing", "admin"]},
    "Approved":  {"next": "RFQ Sent",   "roles": ["purchasing", "admin"]},
    "RFQ Sent":  {"next": "Closed",     "roles": ["purchasing", "admin"]},
    "Closed":    {"next": None,         "roles": []},
}

RFQ_STATUS_FLOW = {
    "Sent":             {"next": "Quotes Received", "roles": ["purchasing", "admin"]},
    "Quotes Received":  {"next": "Evaluated",       "roles": ["purchasing", "admin"]},
    "Evaluated":        {"next": "PO Created",      "roles": ["purchasing", "admin"]},
    "PO Created":       {"next": None,              "roles": []},
}


# ── Session helpers ───────────────────────────────────────
def login_user(user):
    session["user_id"]   = user["id"]
    session["username"]  = user["username"]
    session["full_name"] = user["full_name"]
    session["role"]      = user["role"]


def logout_user():
    session.clear()


def current_user():
    if "user_id" not in session:
        return None
    return {
        "id":        session["user_id"],
        "username":  session["username"],
        "full_name": session["full_name"],
        "role":      session["role"],
    }


def has_permission(permission: str) -> bool:
    user = current_user()
    if not user:
        return False
    return permission in ROLE_PERMISSIONS.get(user["role"], set())


# ── Decorators ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(permission: str):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not has_permission(permission):
                flash("You do not have permission to perform this action.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator
