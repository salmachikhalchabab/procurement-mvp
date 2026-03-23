from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from database import init_db, get_db
from pdf_service import generate_rfq_pdf
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "procurement-mvp-secret-2026"

STATIC_PDF = os.path.join(os.path.dirname(__file__), "static", "rfq_pdfs")


def next_number(prefix, table):
    db = get_db()
    n = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] + 1
    db.close()
    return f"{prefix}-{datetime.now().year}-{n:04d}"


# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────
@app.route("/")
def dashboard():
    db = get_db()
    stats = {
        "total_pr":  db.execute("SELECT COUNT(*) FROM purchase_requests").fetchone()[0],
        "open_pr":   db.execute("SELECT COUNT(*) FROM purchase_requests WHERE status='Open'").fetchone()[0],
        "total_rfq": db.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0],
        "vendors":   db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0],
    }
    recent = db.execute("""
        SELECT pr.pr_number, pr.requester, pr.status, pr.created_at,
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
        db.execute("""
            INSERT INTO purchase_requests
                (pr_number, product_id, raw_material_id, quantity, unit_of_measure,
                 requested_date, requester, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (pr_number, product_id, raw_material_id, quantity, uom, req_date, requester, notes))
        db.commit()
        pr_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()
        flash(f"Purchase Request {pr_number} created successfully!", "success")
        return redirect(url_for("pr_detail", pr_id=pr_id))
    db.close()
    return render_template("pr_create.html", materials=materials, products=products,
                           today=datetime.now().strftime("%Y-%m-%d"))


@app.route("/pr/<int:pr_id>")
def pr_detail(pr_id):
    db = get_db()
    pr = db.execute("""
        SELECT pr.*, rm.name as raw_material_name, p.name as product_name
        FROM purchase_requests pr
        JOIN raw_materials rm ON pr.raw_material_id = rm.id
        LEFT JOIN products p ON pr.product_id = p.id
        WHERE pr.id = ?
    """, (pr_id,)).fetchone()
    rfqs = db.execute("""
        SELECT r.*, v.name as vendor_name
        FROM rfqs r LEFT JOIN vendors v ON r.vendor_id = v.id
        WHERE r.pr_id = ?
        ORDER BY r.created_at DESC
    """, (pr_id,)).fetchall()
    vendors = db.execute("SELECT * FROM vendors ORDER BY name").fetchall()
    db.close()
    if not pr:
        flash("PR not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("pr_detail.html", pr=pr, rfqs=rfqs, vendors=vendors)


@app.route("/pr/list")
def pr_list():
    db = get_db()
    prs = db.execute("""
        SELECT pr.*, rm.name as raw_material_name
        FROM purchase_requests pr
        JOIN raw_materials rm ON pr.raw_material_id = rm.id
        ORDER BY pr.created_at DESC
    """).fetchall()
    db.close()
    return render_template("pr_list.html", prs=prs)


# ─────────────────────────────────────────────
#  RFQ Generation
# ─────────────────────────────────────────────
@app.route("/rfq/generate/<int:pr_id>", methods=["POST"])
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
        dict(pr),
        dict(vendor) if vendor else None
    )
    db.execute("""
        INSERT INTO rfqs (rfq_number, pr_id, vendor_id, quotation_due_date, pdf_path)
        VALUES (?,?,?,?,?)
    """, (rfq_number, pr_id, vendor_id, due_date, f"rfq_pdfs/{pdf_filename}"))
    db.commit()
    db.close()
    flash(f"RFQ {rfq_number} generated successfully!", "success")
    return redirect(url_for("pr_detail", pr_id=pr_id))


@app.route("/rfq/download/<int:rfq_id>")
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
def vendor_list():
    db = get_db()
    vendors = db.execute("""
        SELECT v.*, COUNT(r.id) as rfq_count
        FROM vendors v
        LEFT JOIN rfqs r ON r.vendor_id = v.id
        GROUP BY v.id ORDER BY v.name
    """).fetchall()
    db.close()
    return render_template("vendor_list.html", vendors=vendors)


@app.route("/vendors/create", methods=["GET", "POST"])
def create_vendor():
    if request.method == "POST":
        db = get_db()
        db.execute("""
            INSERT INTO vendors (name, email, country, phone, address, contact_person)
            VALUES (?,?,?,?,?,?)
        """, (request.form["name"].strip(), request.form["email"].strip(),
              request.form["country"].strip(), request.form.get("phone","").strip(),
              request.form.get("address","").strip(), request.form.get("contact_person","").strip()))
        db.commit()
        db.close()
        flash(f"Vendor '{request.form['name']}' added successfully!", "success")
        return redirect(url_for("vendor_list"))
    return render_template("vendor_form.html", vendor=None, action="Create")


@app.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
def edit_vendor(vendor_id):
    db = get_db()
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    if not vendor:
        flash("Vendor not found.", "error")
        return redirect(url_for("vendor_list"))
    if request.method == "POST":
        db.execute("""
            UPDATE vendors SET name=?, email=?, country=?, phone=?, address=?, contact_person=?
            WHERE id=?
        """, (request.form["name"].strip(), request.form["email"].strip(),
              request.form["country"].strip(), request.form.get("phone","").strip(),
              request.form.get("address","").strip(), request.form.get("contact_person","").strip(),
              vendor_id))
        db.commit()
        db.close()
        flash("Vendor updated successfully!", "success")
        return redirect(url_for("vendor_list"))
    db.close()
    return render_template("vendor_form.html", vendor=vendor, action="Edit")


@app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
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
#  Raw Materials Management
# ─────────────────────────────────────────────
@app.route("/materials")
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
def create_material():
    if request.method == "POST":
        name = request.form["name"].strip()
        uom  = request.form["unit_of_measure"].strip()
        db = get_db()
        db.execute("INSERT INTO raw_materials (name, unit_of_measure) VALUES (?,?)", (name, uom))
        db.commit()
        db.close()
        flash(f"Material '{name}' added successfully!", "success")
        return redirect(url_for("material_list"))
    return render_template("material_form.html", material=None, action="Create")


@app.route("/materials/<int:material_id>/edit", methods=["GET", "POST"])
def edit_material(material_id):
    db = get_db()
    material = db.execute("SELECT * FROM raw_materials WHERE id=?", (material_id,)).fetchone()
    if not material:
        flash("Material not found.", "error")
        return redirect(url_for("material_list"))
    if request.method == "POST":
        db.execute("UPDATE raw_materials SET name=?, unit_of_measure=? WHERE id=?",
                   (request.form["name"].strip(), request.form["unit_of_measure"].strip(), material_id))
        db.commit()
        db.close()
        flash("Material updated successfully!", "success")
        return redirect(url_for("material_list"))
    db.close()
    return render_template("material_form.html", material=material, action="Edit")


@app.route("/materials/<int:material_id>/delete", methods=["POST"])
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
def product_list():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    db.close()
    return render_template("product_list.html", products=products)


@app.route("/products/create", methods=["GET", "POST"])
def create_product():
    if request.method == "POST":
        name = request.form["name"].strip()
        code = request.form["code"].strip().upper()
        db = get_db()
        try:
            db.execute("INSERT INTO products (name, code) VALUES (?,?)", (name, code))
            db.commit()
            flash(f"Product '{name}' added successfully!", "success")
        except Exception:
            flash(f"Code '{code}' already exists.", "error")
        db.close()
        return redirect(url_for("product_list"))
    return render_template("product_form.html", product=None, action="Create")


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
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
            flash("Product updated successfully!", "success")
        except Exception:
            flash(f"Code '{code}' already exists.", "error")
        db.close()
        return redirect(url_for("product_list"))
    db.close()
    return render_template("product_form.html", product=product, action="Edit")


@app.route("/products/<int:product_id>/delete", methods=["POST"])
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

init_db()
app.run(debug=True, port=5050)