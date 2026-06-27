# Procurement Process Digitalization MVP

> AVERROA IT Launchpad — Syria Cohort | Assignment 2  
> Built by [Salma Chikh Alchabab](https://github.com/salmachikhalchabab)

## Demo

📹 **[Watch Demo on Loom](https://www.loom.com/share/cdc76cc989994c14be3e0cee8a4db981)**

📄 **[Sample RFQ PDF](RFQ-2026-0002.pdf)** — Example of a generated vendor quotation request

---

A fully functional web application that digitalizes the manual procurement process — from Purchase Request creation to professional RFQ PDF generation, with user authentication and status tracking.

---

## Features

- **User Authentication** — Login system with role-based access (Admin, Purchasing, Planning, Viewer)
- **Purchase Request (PR)** — Create structured PRs with auto-generated reference numbers
- **RFQ PDF Generation** — Professional vendor-ready PDF documents with one click
- **Status Tracking** — PR lifecycle: Draft → Submitted → Approved → RFQ Sent → Closed
- **Vendor Management** — Full CRUD for supplier database
- **Materials Management** — Manage raw materials and units of measure
- **Products Management** — Manage finished products
- **User Management** — Admin can create and manage system users
- **Audit Trail** — Full status change history with timestamps

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + Flask |
| Database | SQLite (sqlite3 built-in) |
| PDF Generation | ReportLab |
| Frontend | HTML + Jinja2 + CSS |
| Auth | bcrypt + Flask sessions |
| Config | python-dotenv |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/salmachikhalchabab/procurement-mvp.git
cd procurement-mvp

# 2. Install dependencies
pip install flask reportlab bcrypt python-dotenv

# 3. Create your .env file
copy .env.example .env

# 4. Edit .env and set your values
# ADMIN_PASSWORD=your_secure_password

# 5. Run
python main.py
```

Open: **http://127.0.0.1:5050**

---

## Environment Variables

```env
SECRET_KEY=your-random-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
ADMIN_FULLNAME=System Administrator
```

> ⚠️ Never commit `.env` to Git

---

## Project Structure

```
procurement-mvp/
├── main.py           ← Flask app + all routes
├── database.py       ← SQLite setup + migrations
├── auth.py           ← Authentication + roles
├── pdf_service.py    ← RFQ PDF generator
├── .env.example      ← Environment variables template
├── static/
│   └── rfq_pdfs/     ← Generated PDFs
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── pr_*.html
    ├── vendor_*.html
    ├── material_*.html
    ├── product_*.html
    └── user_*.html
```

---

## User Roles

| Role | Access |
|------|--------|
| Admin | Full access + user management |
| Purchasing | Vendors, PRs, RFQ generation |
| Planning | Create PRs only |
| Viewer | Read-only |

---

## PR Status Flow

```
Draft → Submitted → Approved → RFQ Sent → Closed
```

---

## Reset

```bash
# Windows
del procurement.db

# Mac/Linux  
rm procurement.db

# Restart
python main.py
```

---

## Author

**Salma Chikh Alchabab**  
[github.com/salmachikhalchabab](https://github.com/salmachikhalchabab)
