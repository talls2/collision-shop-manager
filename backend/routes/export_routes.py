"""
Export & PDF routes.
GET /api/exports/estimate/{id}/pdf - estimate PDF
GET /api/exports/ro/{id}/invoice-pdf - invoice PDF
GET /api/exports/ro/{id}/work-order-pdf - work order PDF
GET /api/exports/quickbooks - QuickBooks IIF export
GET /api/exports/xml - Generic XML export
GET /api/exports/mitchell-connect - Mitchell Connect XML export
"""
import io
import sqlite3
import os
import tempfile
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi import BackgroundTasks
from typing import Optional
from services.pdf_service import (
    generate_estimate_pdf, generate_invoice_pdf, generate_work_order_pdf
)
from services.export_service import ExportService
from services.repair_order_service import RepairOrderService
from services.estimate_service import EstimateService
from config.database import get_db, row_to_dict, rows_to_list, DB_PATH
from routes.auth_routes import require_admin
from fastapi import Request

router = APIRouter(prefix="/api/exports", tags=["exports"])
export_svc = ExportService()
ro_svc = RepairOrderService()
est_svc = EstimateService()


def _get_shop():
    with get_db() as db:
        row = db.execute("SELECT * FROM body_shop LIMIT 1").fetchone()
    return row_to_dict(row) if row else None


@router.get("/estimate/{estimate_id}/pdf")
def estimate_pdf(estimate_id: int):
    """Generate and download an estimate as PDF.

    Same data source as the JSON API (`service.get_estimate`) so any field
    surfaced in the UI is automatically available in the PDF — including
    customer address and billing address.
    """
    est = est_svc.get_estimate(estimate_id)
    if not est:
        raise HTTPException(status_code=404, detail="Estimate not found")
    lines = est.get("lines") or []

    shop = _get_shop()
    buf = generate_estimate_pdf(est, lines, shop)
    filename = f"Estimate_{est.get('estimate_number', estimate_id)}.pdf"

    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/ro/{ro_id}/invoice-pdf")
def invoice_pdf(ro_id: int):
    """Generate and download an invoice PDF for a repair order.

    Uses the SAME data source as the JSON API (`service.get_ro`) so any field
    we surface in the UI is automatically available in the PDF — including
    customer address, billing address, vehicle type, etc.
    """
    ro = ro_svc.get_ro(ro_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    with get_db() as db:
        lines = rows_to_list(db.execute(
            "SELECT * FROM ro_lines WHERE ro_id = ? ORDER BY line_number",
            (ro_id,)
        ).fetchall())
        payments = rows_to_list(db.execute(
            "SELECT * FROM payments WHERE ro_id = ? ORDER BY payment_date",
            (ro_id,)
        ).fetchall())

    shop = _get_shop()
    buf = generate_invoice_pdf(ro, lines, payments, shop)
    filename = f"Invoice_{ro.get('ro_number', ro_id)}.pdf"

    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/ro/{ro_id}/work-order-pdf")
def work_order_pdf(ro_id: int):
    """Generate and download a work order PDF for the shop floor."""
    ro = ro_svc.get_ro(ro_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    with get_db() as db:
        lines = rows_to_list(db.execute(
            "SELECT * FROM ro_lines WHERE ro_id = ? ORDER BY line_number",
            (ro_id,)
        ).fetchall())

    shop = _get_shop()
    buf = generate_work_order_pdf(ro, lines, shop)
    filename = f"WorkOrder_{ro.get('ro_number', ro_id)}.pdf"

    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/quickbooks")
def quickbooks_export(date_from: Optional[str] = Query(None),
                      date_to: Optional[str] = Query(None)):
    """Export data as QuickBooks IIF file."""
    try:
        content = export_svc.export_quickbooks_iif(date_from, date_to)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=shop_manager_export.iif"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xml")
def xml_export(date_from: Optional[str] = Query(None),
               date_to: Optional[str] = Query(None)):
    """Export data as generic XML."""
    try:
        content = export_svc.export_xml(date_from, date_to)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=shop_manager_export.xml"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mitchell-connect")
def mitchell_connect_export(date_from: Optional[str] = Query(None),
                            date_to: Optional[str] = Query(None)):
    """Export estimates as Mitchell Connect compatible XML."""
    try:
        content = export_svc.export_mitchell_connect_xml(date_from, date_to)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=mitchell_connect_export.xml"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estimates-csv")
def estimates_csv_export(date_from: Optional[str] = Query(None),
                         date_to: Optional[str] = Query(None),
                         status: Optional[str] = Query(None)):
    """Export estimates to CSV for a date range, optionally filtered by status."""
    import csv, io as _io
    from datetime import date as _date_t

    query = """
        SELECT e.estimate_number, e.estimate_date, e.loss_date, e.status,
               e.point_of_impact, e.damage_description,
               c.first_name, c.last_name, c.company_name, c.phone_home, c.email,
               v.year, v.make, v.model, v.vin, v.color, v.license_plate,
               ic.company_name AS insurance_name, e.claim_number, e.policy_number,
               e.deductible,
               emp.first_name AS estimator_first, emp.last_name AS estimator_last,
               e.subtotal_labor, e.subtotal_parts, e.subtotal_paint, e.subtotal_other,
               e.tax_amount, e.tax_exempt, e.total_amount,
               e.created_at
        FROM estimates e
        LEFT JOIN customers c ON e.customer_id = c.id
        LEFT JOIN vehicles v ON e.vehicle_id = v.id
        LEFT JOIN insurance_companies ic ON e.insurance_company_id = ic.id
        LEFT JOIN employees emp ON e.estimator_id = emp.id
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND e.estimate_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND e.estimate_date <= ?"
        params.append(date_to)
    if status:
        query += " AND e.status = ?"
        params.append(status)
    query += " ORDER BY e.estimate_date DESC, e.estimate_number DESC"

    with get_db() as db:
        rows = rows_to_list(db.execute(query, params).fetchall())

    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Estimate #", "Date", "Status", "Customer", "Phone", "Email",
        "Vehicle", "VIN", "Color", "Plate",
        "Insurance", "Claim #", "Policy #", "Deductible",
        "Loss Date", "Point of Impact", "Damage Description",
        "Estimator",
        "Subtotal Labor", "Subtotal Parts", "Subtotal Paint", "Subtotal Other",
        "Tax", "Tax Exempt", "Total",
        "Created",
    ])
    for r in rows:
        cust = r.get("company_name") or " ".join(x for x in [r.get("first_name"), r.get("last_name")] if x) or "—"
        veh = " ".join(str(x) for x in [r.get("year"), r.get("make"), r.get("model")] if x) or "—"
        estimator = " ".join(x for x in [r.get("estimator_first"), r.get("estimator_last")] if x) or ""
        w.writerow([
            r.get("estimate_number") or "",
            r.get("estimate_date") or "",
            r.get("status") or "",
            cust,
            r.get("phone_home") or "",
            r.get("email") or "",
            veh,
            r.get("vin") or "",
            r.get("color") or "",
            r.get("license_plate") or "",
            r.get("insurance_name") or "",
            r.get("claim_number") or "",
            r.get("policy_number") or "",
            f"{r.get('deductible') or 0:.2f}",
            r.get("loss_date") or "",
            r.get("point_of_impact") or "",
            (r.get("damage_description") or "").replace("\n", " ").replace("\r", " "),
            estimator,
            f"{r.get('subtotal_labor') or 0:.2f}",
            f"{r.get('subtotal_parts') or 0:.2f}",
            f"{r.get('subtotal_paint') or 0:.2f}",
            f"{r.get('subtotal_other') or 0:.2f}",
            f"{r.get('tax_amount') or 0:.2f}",
            "Yes" if r.get("tax_exempt") else "No",
            f"{r.get('total_amount') or 0:.2f}",
            r.get("created_at") or "",
        ])

    if rows:
        sums = {k: sum(float(r.get(col) or 0) for r in rows) for k, col in
                [("labor","subtotal_labor"),("parts","subtotal_parts"),("paint","subtotal_paint"),
                 ("other","subtotal_other"),("tax","tax_amount"),("total","total_amount")]}
        w.writerow([])
        w.writerow([f"TOTALS ({len(rows)} estimates)"] + [""] * 17 +
                   [f"{sums['labor']:.2f}", f"{sums['parts']:.2f}", f"{sums['paint']:.2f}", f"{sums['other']:.2f}",
                    f"{sums['tax']:.2f}", "", f"{sums['total']:.2f}", ""])

    today = _date_t.today().isoformat()
    range_part = ""
    if date_from or date_to:
        range_part = f"_{date_from or 'start'}_to_{date_to or today}"
    filename = f"estimates{range_part}.csv"

    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),  # BOM so Excel reads UTF-8 right
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/db-backup")
def db_backup(request: Request, background_tasks: BackgroundTasks):
    """
    Admin-only: stream a clean SQLite snapshot of the entire shop database.

    Uses SQLite's online backup API (Connection.backup) so the snapshot is
    transactionally consistent even while the app is being written to — no
    downtime or risk of corruption. Writes to a temp file, streams it, then
    deletes the temp via a background task.
    """
    require_admin(request)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    fd, tmp_path = tempfile.mkstemp(prefix=f"shop_backup_{timestamp}_", suffix=".db")
    os.close(fd)
    try:
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Backup failed: {e}")

    filename = f"shop_backup_{timestamp}.db"
    background_tasks.add_task(_safe_remove, tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/x-sqlite3",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
