"""
Shop Manager - Main Application Entry Point.
Modern web-based replacement for Mitchell Estimating ABS.

Architecture:
    Routes → Services → Repositories → SQLite
    Each layer has clear responsibility separation.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from config.database import get_connection
from config.schema import TABLES, INDEXES
from config.seed import seed_initial_data
from config.migrations import run_migrations

from routes import (
    dashboard_router,
    customer_router,
    vehicle_router,
    estimate_router,
    repair_order_router,
    employee_router,
    vendor_router,
    insurance_router,
    timecard_router,
    shop_router,
    report_router,
    production_router,
    auth_router,
    export_router,
    tecstation_router,
    parts_catalog_router,
)

# ─── App Setup ───
app = FastAPI(
    title="Shop Manager",
    description="Modern auto body shop management system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Route Modules ───
app.include_router(dashboard_router)
app.include_router(customer_router)
app.include_router(vehicle_router)
app.include_router(estimate_router)
app.include_router(repair_order_router)
app.include_router(employee_router)
app.include_router(vendor_router)
app.include_router(insurance_router)
app.include_router(timecard_router)
app.include_router(shop_router)
app.include_router(report_router)
app.include_router(production_router)
app.include_router(auth_router)
app.include_router(export_router)
app.include_router(tecstation_router)
app.include_router(parts_catalog_router)


# ─── Database Initialization ───
@app.on_event("startup")
def startup():
    """Create tables, indexes, and seed demo data on first run."""
    conn = get_connection()
    cur = conn.cursor()
    for table_sql in TABLES:
        cur.execute(table_sql)
    for index_sql in INDEXES:
        cur.execute(index_sql)
    conn.commit()
    run_migrations(conn)
    seed_initial_data(conn)
    conn.close()


# ─── Serve Frontend ───
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
def serve_index():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Shop Manager API running. Frontend not found."}

@app.get("/logo.png")
def serve_logo():
    logo = os.path.join(FRONTEND_DIR, "logo.png")
    if os.path.exists(logo):
        return FileResponse(logo, media_type="image/png")
    return {"error": "Logo not found"}

@app.get("/parts-catalog.js")
def serve_parts_catalog():
    f = os.path.join(FRONTEND_DIR, "parts-catalog.js")
    if os.path.exists(f):
        return FileResponse(f, media_type="application/javascript")
    return {"error": "Parts catalog not found"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
