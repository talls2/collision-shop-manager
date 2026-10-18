# Collision Shop Manager

A full shop-management system for collision and heavy-truck repair shops, built in Python with a single-page web front end.

## What it does
- **Estimates and repair orders**: line items, labor, parts and paint, status tracking, PDF export
- **Customers and vehicles**: individuals and fleet accounts, VIN-based vehicle records
- **Insurance**: carriers, claims and adjuster details attached to repair orders
- **Shop floor**: production board, technician time clock and timecards, labor allocation per repair order
- **Parts catalog** and vendor records
- **Payments and reports**, with printable invoices
- **Authentication**: session tokens with expiry and role-based access (owner, manager, technician, front desk)
- **Data migration**: an idempotent importer for **Mitchell ABS7 XML and CSI exports** (`backend/scripts/import_mitchell.py`), so a shop can move its historical estimates off legacy estimating software

## Architecture
- `backend/` - routes, services and repositories in layers, SQLite storage with schema migrations, PDF generation
- `frontend/` - a single-page React UI served by the backend
- `Procfile` - ready for a Heroku-style deploy

## Run it locally
```bash
pip install -r requirements.txt
python backend/app.py
```
The database is seeded with fictional demo data (555 phone numbers, example.com emails). Insurance carriers and parts vendors in the seed use their public head-office details.

## Background
This is a **white-label version of a product in production use by clients**. I built it for a family of collision and heavy-truck repair shops in Massachusetts. This public copy has the client's branding and contact details replaced with demo values.
