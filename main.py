from flask import (Flask, render_template, request, redirect,
                   url_for, send_file, flash, session)
from database import init_db, get_db, hash_password, check_password
from pdf_service import generate_rfq_pdf
from auth import (login_user, logout_user, current_user, has_permission,
                  login_required, role_required, permission_required,
                  ROLE_LABELS, PR_STATUS_FLOW, RFQ_STATUS_FLOW)
from datetime import datetime
import os

# ── Load environment variables from .env file ─────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — use system env vars

app = Flask(__name__)
app.secret_key = "procurement-mvp-secret-2026"

STATIC_PDF = os.path.join(os.path.dirname(__file__), "static", "rfq_pdfs")


# ── Context processor — inject user into all templates ────
@app.context_processor
def inject_user():
    return {
        "current_user": current_user(),
        "has_permission": has_permission,
        "ROLE_LABELS": ROLE_LABELS,
    }


def next_number(prefix, table):
    db = get_db()
    n = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] + 1
    db.close()
    return f"{prefix}-{datetime.now().year}-{n:04d}"


# ─────────────────────────────────────────────
#  Auth Routes
# ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1",
            (username,)
        ).fetchone()
        db.close()
        if user and check_password(password, user["password_hash"]):
            login_user(user)
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    stats = {
        "total_pr":  db.execute("SELECT COUNT(*) FROM purchase_requests").fetchone()[0],
        "open_pr":   db.execute("SELECT COUNT(*) FROM purchase_requests WHERE status NOT IN ('Closed')").fetchone()[0],
        "total_rfq": db.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0],
        "vendors":   db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0],
    }
    recent = db.execute("""
        SELECT pr.id, pr.pr_number, pr.requester, pr.status, pr.created_at,
               rm.name as material, pr.quantity, pr.unit_of_measure
        FROM purchase_requests pr
        JOIN raw_materials rm ON pr.raw_material_id = rm.id
        ORDER BY pr.created_at DESC LIMIT 8
    """).fetchall()
    db.close()
    return render_template("dashboard.html", stats=stats, recent=recent)


# ─────────────────────────────────────────────
#  Purchase Request
# ─────────────────────────────────────────────
@app.route("/pr/create", methods=["GET", "POST"])
@login_required
@permission_required("can_create_pr")
def create_pr():
    db = get_db()
    materials = db.execute("SELECT * FROM raw_materials ORDER BY name").fetchall()
    products  = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    if request.method == "POST":
        pr_number       = next_number("PR", "purchase_requests")
        raw_material_id = request.form["raw_material_id"]
        product_id      = request.form.get("product_id") or None
        quantity        = request.form["quantity"]
        uom             = request.form["unit_of_measure"]
        req_date        = request.form["requested_date"]
        requester       = request.form["requester"].strip()
        notes           = request.form.get("notes", "").strip()
        user            = current_user()

        db.execute("""
            INSERT INTO purchase_requests
                (pr_number, product_id, raw_material_id, quantity, unit_of_measure,
                 requested_date, requester, notes, status, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (pr_number, product_id, raw_material_id, quantity, uom,
              req_date, requester, notes, "Draft", user["id"]))
        db.commit()
        pr_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Log status
        db.execute("""
            INSERT INTO pr_status_log (pr_id, old_status, new_status, changed_by, note)
            VALUES (?,?,?,?,?)
        """, (pr_id, None, "Draft", user["id"], "PR created"))
        db.commit()
        db.close()

        flash(f"Purchase Request {pr_number} created!", "success")
        return redirect(url_for("pr_detail", pr_id=pr_id))
    db.close()
    return render_template("pr_create.html", materials=materials, products=products,
                           today=datetime.now().strftime("%Y-%m-%d"))


@app.route("/pr/<int:pr_id>")
@login_required
def pr_detail(pr_id):
    db = get_db()
    pr = db.execute("""
        SELECT pr.*, rm.name as raw_material_name, p.name as product_name,
               u.full_name as created_by_name
        FROM purchase_requests pr
        JOIN raw_materials rm ON pr.raw_material_id = rm.id
        LEFT JOIN products p ON pr.product_id = p.id
        LEFT JOIN users u ON pr.created_by = u.id
        WHERE pr.id = ?
    """, (pr_id,)).fetchone()
    rfqs = db.execute("""
        SELECT r.*, v.name as vendor_name
        FROM rfqs r LEFT JOIN vendors v ON r.vendor_id = v.id
        WHERE r.pr_id = ? ORDER BY r.created_at DESC
    """, (pr_id,)).fetchall()
    vendors  = db.execute("SELECT * FROM vendors ORDER BY name").fetchall()
    status_log = db.execute("""
        SELECT l.*, u.full_name as changed_by_name
        FROM pr_status_log l
        LEFT JOIN users u ON l.changed_by = u.id
        WHERE l.pr_id = ? ORDER BY l.changed_at ASC
    """, (pr_id,)).fetchall()
    db.close()
    if not pr:
        flash("PR not found.", "error")
        return redirect(url_for("dashboard"))

    next_status = PR_STATUS_FLOW.get(pr["status"], {}).get("next")
    can_advance = (
        next_status and
        current_user() and
        current_user()["role"] in PR_STATUS_FLOW.get(pr["status"], {}).get("roles", [])
    )
    return render_template("pr_detail.html", pr=pr, rfqs=rfqs, vendors=vendors,
                           status_log=status_log, next_status=next_status,
                           can_advance=can_advance)


@app.route("/pr/<int:pr_id>/advance", methods=["POST"])
@login_required
def advance_pr_status(pr_id):
    db = get_db()
    pr = db.execute("SELECT * FROM purchase_requests WHERE id=?", (pr_id,)).fetchone()
    if not pr:
        flash("PR not found.", "error")
        return redirect(url_for("dashboard"))

    flow = PR_STATUS_FLOW.get(pr["status"], {})
    next_status = flow.get("next")
    allowed_roles = flow.get("roles", [])
    user = current_user()
    note = request.form.get("note", "").strip()

    if not next_status:
        flash("This PR cannot be advanced further.", "error")
        return redirect(url_for("pr_detail", pr_id=pr_id))
    if user["role"] not in allowed_roles:
        flash("You do not have permission to advance this PR.", "error")
        return redirect(url_for("pr_detail", pr_id=pr_id))

    old_status = pr["status"]
    db.execute("UPDATE purchase_requests SET status=?, updated_at=datetime('now') WHERE id=?",
               (next_status, pr_id))
    db.execute("""
        INSERT INTO pr_status_log (pr_id, old_status, new_status, changed_by, note)
        VALUES (?,?,?,?,?)
    """, (pr_id, old_status, next_status, user["id"], note or f"Status changed to {next_status}"))
    db.commit()
    db.close()
    flash(f"PR status updated: {old_status} → {next_status}", "success")
    return redirect(url_for("pr_detail", pr_id=pr_id))


@app.route("/pr/list")
@login_required
def pr_list():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = """
        SELECT pr.*, rm.name as raw_material_name
        FROM purchase_requests pr
        JOIN raw_materials rm ON pr.raw_material_id = rm.id
    """
    if status_filter:
        prs = db.execute(query + " WHERE pr.status=? ORDER BY pr.created_at DESC",
                         (status_filter,)).fetchall()
    else:
        prs = db.execute(query + " ORDER BY pr.created_at DESC").fetchall()
    db.close()
    statuses = ["Draft", "Submitted", "Approved", "RFQ Sent", "Closed"]
    return render_template("pr_list.html", prs=prs, statuses=statuses,
                           current_status=status_filter)


# ─────────────────────────────────────────────
#  RFQ Generation
# ─────────────────────────────────────────────
@app.route("/rfq/generate/<int:pr_id>", methods=["POST"])
@login_required
@permission_required("can_generate_rfq")
def generate_rfq(pr_id):
    db = get_db()
    pr = db.execute("""
        SELECT pr.*, rm.name as raw_material_name
        FROM purchase_requests pr
        JOIN raw_materials rm ON pr.raw_material_id = rm.id
        WHERE pr.id = ?
    """, (pr_id,)).fetchone()
    vendor_id  = request.form.get("vendor_id") or None
    due_date   = request.form.get("due_date", "")
    rfq_number = next_number("RFQ", "rfqs")
    vendor = None
    if vendor_id:
        vendor = db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    pdf_filename = generate_rfq_pdf(
        {"rfq_number": rfq_number, "quotation_due_date": due_date},
        dict(pr), dict(vendor) if vendor else None
    )
    db.execute("""
        INSERT INTO rfqs (rfq_number, pr_id, vendor_id, quotation_due_date, pdf_path, status)
        VALUES (?,?,?,?,?,?)
    """, (rfq_number, pr_id, vendor_id, due_date, f"rfq_pdfs/{pdf_filename}", "Sent"))

    # Auto-advance PR to RFQ Sent if Approved
    if pr["status"] == "Approved":
        user = current_user()
        db.execute("UPDATE purchase_requests SET status='RFQ Sent', updated_at=datetime('now') WHERE id=?",
                   (pr_id,))
        db.execute("""
            INSERT INTO pr_status_log (pr_id, old_status, new_status, changed_by, note)
            VALUES (?,?,?,?,?)
        """, (pr_id, "Approved", "RFQ Sent", user["id"], f"RFQ {rfq_number} generated"))

    db.commit()
    db.close()
    flash(f"RFQ {rfq_number} generated successfully!", "success")
    return redirect(url_for("pr_detail", pr_id=pr_id))


@app.route("/rfq/download/<int:rfq_id>")
@login_required
def download_rfq(rfq_id):
    db = get_db()
    rfq = db.execute("SELECT * FROM rfqs WHERE id=?", (rfq_id,)).fetchone()
    db.close()
    if not rfq or not rfq["pdf_path"]:
        flash("PDF not found.", "error")
        return redirect(url_for("dashboard"))
    full_path = os.path.join(os.path.dirname(__file__), "static", "rfq_pdfs",
                             os.path.basename(rfq["pdf_path"]))
    return send_file(full_path, as_attachment=True,
                     download_name=os.path.basename(rfq["pdf_path"]))


# ─────────────────────────────────────────────
#  Vendor Management
# ─────────────────────────────────────────────
@app.route("/vendors")
@login_required
def vendor_list():
    db = get_db()
    vendors = db.execute("""
        SELECT v.*, COUNT(r.id) as rfq_count
        FROM vendors v LEFT JOIN rfqs r ON r.vendor_id = v.id
        GROUP BY v.id ORDER BY v.name
    """).fetchall()
    db.close()
    return render_template("vendor_list.html", vendors=vendors)


@app.route("/vendors/create", methods=["GET", "POST"])
@login_required
@permission_required("can_manage_vendors")
def create_vendor():
    if request.method == "POST":
        db = get_db()
        db.execute("""
            INSERT INTO vendors (name, email, country, phone, address, contact_person)
            VALUES (?,?,?,?,?,?)
        """, (request.form["name"].strip(), request.form["email"].strip(),
              request.form["country"].strip(), request.form.get("phone","").strip(),
              request.form.get("address","").strip(), request.form.get("contact_person","").strip()))
        db.commit(); db.close()
        flash(f"Vendor '{request.form['name']}' added!", "success")
        return redirect(url_for("vendor_list"))
    return render_template("vendor_form.html", vendor=None, action="Create")


@app.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("can_manage_vendors")
def edit_vendor(vendor_id):
    db = get_db()
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    if not vendor:
        flash("Vendor not found.", "error")
        return redirect(url_for("vendor_list"))
    if request.method == "POST":
        db.execute("""
            UPDATE vendors SET name=?,email=?,country=?,phone=?,address=?,contact_person=?
            WHERE id=?
        """, (request.form["name"].strip(), request.form["email"].strip(),
              request.form["country"].strip(), request.form.get("phone","").strip(),
              request.form.get("address","").strip(), request.form.get("contact_person","").strip(),
              vendor_id))
        db.commit(); db.close()
        flash("Vendor updated!", "success")
        return redirect(url_for("vendor_list"))
    db.close()
    return render_template("vendor_form.html", vendor=vendor, action="Edit")


@app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
@login_required
@permission_required("can_manage_vendors")
def delete_vendor(vendor_id):
    db = get_db()
    vendor = db.execute("SELECT name FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    if vendor:
        db.execute("DELETE FROM vendors WHERE id=?", (vendor_id,))
        db.commit()
        flash(f"Vendor '{vendor['name']}' deleted.", "success")
    db.close()
    return redirect(url_for("vendor_list"))


# ─────────────────────────────────────────────
#  Materials Management
# ─────────────────────────────────────────────
@app.route("/materials")
@login_required
def material_list():
    db = get_db()
    materials = db.execute("""
        SELECT rm.*, COUNT(pr.id) as pr_count
        FROM raw_materials rm
        LEFT JOIN purchase_requests pr ON pr.raw_material_id = rm.id
        GROUP BY rm.id ORDER BY rm.name
    """).fetchall()
    db.close()
    return render_template("material_list.html", materials=materials)


@app.route("/materials/create", methods=["GET", "POST"])
@login_required
@permission_required("can_manage_materials")
def create_material():
    if request.method == "POST":
        name = request.form["name"].strip()
        uom  = request.form["unit_of_measure"].strip()
        db = get_db()
        db.execute("INSERT INTO raw_materials (name, unit_of_measure) VALUES (?,?)", (name, uom))
        db.commit(); db.close()
        flash(f"Material '{name}' added!", "success")
        return redirect(url_for("material_list"))
    return render_template("material_form.html", material=None, action="Create")


@app.route("/materials/<int:material_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("can_manage_materials")
def edit_material(material_id):
    db = get_db()
    material = db.execute("SELECT * FROM raw_materials WHERE id=?", (material_id,)).fetchone()
    if not material:
        flash("Material not found.", "error")
        return redirect(url_for("material_list"))
    if request.method == "POST":
        db.execute("UPDATE raw_materials SET name=?, unit_of_measure=? WHERE id=?",
                   (request.form["name"].strip(), request.form["unit_of_measure"].strip(), material_id))
        db.commit(); db.close()
        flash("Material updated!", "success")
        return redirect(url_for("material_list"))
    db.close()
    return render_template("material_form.html", material=material, action="Edit")


@app.route("/materials/<int:material_id>/delete", methods=["POST"])
@login_required
@permission_required("can_manage_materials")
def delete_material(material_id):
    db = get_db()
    material = db.execute("SELECT name FROM raw_materials WHERE id=?", (material_id,)).fetchone()
    if material:
        db.execute("DELETE FROM raw_materials WHERE id=?", (material_id,))
        db.commit()
        flash(f"Material '{material['name']}' deleted.", "success")
    db.close()
    return redirect(url_for("material_list"))


# ─────────────────────────────────────────────
#  Products Management
# ─────────────────────────────────────────────
@app.route("/products")
@login_required
def product_list():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    db.close()
    return render_template("product_list.html", products=products)


@app.route("/products/create", methods=["GET", "POST"])
@login_required
@permission_required("can_manage_products")
def create_product():
    if request.method == "POST":
        name = request.form["name"].strip()
        code = request.form["code"].strip().upper()
        db = get_db()
        try:
            db.execute("INSERT INTO products (name, code) VALUES (?,?)", (name, code))
            db.commit()
            flash(f"Product '{name}' added!", "success")
        except Exception:
            flash(f"Code '{code}' already exists.", "error")
        db.close()
        return redirect(url_for("product_list"))
    return render_template("product_form.html", product=None, action="Create")


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("can_manage_products")
def edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("product_list"))
    if request.method == "POST":
        name = request.form["name"].strip()
        code = request.form["code"].strip().upper()
        try:
            db.execute("UPDATE products SET name=?, code=? WHERE id=?", (name, code, product_id))
            db.commit()
            flash("Product updated!", "success")
        except Exception:
            flash(f"Code '{code}' already exists.", "error")
        db.close()
        return redirect(url_for("product_list"))
    db.close()
    return render_template("product_form.html", product=product, action="Edit")


@app.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
@permission_required("can_manage_products")
def delete_product(product_id):
    db = get_db()
    product = db.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()
    if product:
        db.execute("DELETE FROM products WHERE id=?", (product_id,))
        db.commit()
        flash(f"Product '{product['name']}' deleted.", "success")
    db.close()
    return redirect(url_for("product_list"))


# ─────────────────────────────────────────────
#  User Management (Admin only)
# ─────────────────────────────────────────────
@app.route("/users")
@login_required
@role_required("admin")
def user_list():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY role, username").fetchall()
    db.close()
    return render_template("user_list.html", users=users)


@app.route("/users/create", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_user():
    if request.method == "POST":
        username  = request.form["username"].strip()
        full_name = request.form["full_name"].strip()
        password  = request.form["password"]
        role      = request.form["role"]
        db = get_db()
        try:
            db.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?,?,?,?)
            """, (username, hash_password(password), full_name, role))
            db.commit()
            flash(f"User '{username}' created!", "success")
        except Exception:
            flash(f"Username '{username}' already exists.", "error")
        db.close()
        return redirect(url_for("user_list"))
    return render_template("user_form.html", user=None, action="Create",
                           roles=["admin","purchasing","planning","viewer"])


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_user(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("user_list"))
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        role      = request.form["role"]
        is_active = 1 if request.form.get("is_active") else 0
        new_pw    = request.form.get("new_password", "").strip()
        if new_pw:
            db.execute("UPDATE users SET full_name=?,role=?,is_active=?,password_hash=? WHERE id=?",
                       (full_name, role, is_active, hash_password(new_pw), user_id))
        else:
            db.execute("UPDATE users SET full_name=?,role=?,is_active=? WHERE id=?",
                       (full_name, role, is_active, user_id))
        db.commit(); db.close()
        flash("User updated!", "success")
        return redirect(url_for("user_list"))
    db.close()
    return render_template("user_form.html", user=user, action="Edit",
                           roles=["admin","purchasing","planning","viewer"])


# ─────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
