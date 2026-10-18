"""
Report routes: shop reports as JSON or downloadable PDF.

JSON:
    GET /production-summary (?start_date=, ?end_date=)
    GET /ar-aging
    GET /employee-productivity
    GET /parts-summary
    GET /cycle-time

PDF (same data, formatted for print):
    GET /production-summary/pdf (?start_date=, ?end_date=)
    GET /ar-aging/pdf
    GET /employee-productivity/pdf
    GET /parts-summary/pdf
    GET /cycle-time/pdf
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from services.report_service import ReportService
from services.pdf_service import generate_report_pdf
from config.database import get_db, row_to_dict

router = APIRouter(prefix="/api/reports", tags=["reports"])
service = ReportService()


# ── Helpers ─────────────────────────────────────────────────────
def _shop():
    with get_db() as db:
        row = db.execute("SELECT * FROM body_shop LIMIT 1").fetchone()
    return row_to_dict(row) if row else None


def _money(n):
    try:
        return f"${float(n or 0):,.2f}"
    except Exception:
        return "$0.00"


def _pdf_response(buf, filename):
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _date_range_subtitle(start_date, end_date):
    if not start_date and not end_date:
        return "Date range: All time"
    return f"Date range: {start_date or 'beginning'} → {end_date or 'today'}"


def _cust_name(row):
    if row.get("company_name"):
        return row["company_name"]
    return " ".join(x for x in [row.get("first_name"), row.get("last_name")] if x).strip() or "—"


# ── JSON endpoints ──────────────────────────────────────────────
@router.get("/production-summary")
def get_production_summary(start_date: Optional[str] = Query(None),
                           end_date: Optional[str] = Query(None)):
    try:
        return service.production_summary(start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ar-aging")
def get_ar_aging():
    try:
        return service.ar_aging()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employee-productivity")
def get_employee_productivity():
    try:
        return service.employee_productivity()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parts-summary")
def get_parts_summary():
    try:
        return service.parts_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cycle-time")
def get_cycle_time():
    try:
        return service.cycle_time()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PDF endpoints ───────────────────────────────────────────────
@router.get("/production-summary/pdf")
def production_summary_pdf(start_date: Optional[str] = Query(None),
                            end_date: Optional[str] = Query(None)):
    p = service.production_summary(start_date=start_date, end_date=end_date)

    summary_stats = [
        ("Active ROs",        str(p.get("active_ros") or 0)),
        ("Completed ROs",     str(p.get("completed_ros") or 0)),
        ("Total Billed",      _money(p.get("total_billed"))),
        ("Collected",         _money(p.get("total_collected"))),
        ("Outstanding",       _money(p.get("total_outstanding"))),
        ("Labor",             _money(p.get("total_labor"))),
        ("Parts",             _money(p.get("total_parts"))),
        ("Paint",             _money(p.get("total_paint"))),
    ]

    headers = ["Status", "Count", "Total Billed", "Amount Paid", "Balance Due"]
    rows = []
    for r in p.get("repair_orders_by_status") or []:
        rows.append([
            (r.get("status") or "").title(),
            str(r.get("count") or 0),
            _money(r.get("total_amount")),
            _money(r.get("amount_paid")),
            _money(r.get("balance_due")),
        ])

    buf = generate_report_pdf(
        title="Production Summary",
        subtitle=_date_range_subtitle(start_date, end_date),
        summary_stats=summary_stats,
        headers=headers,
        rows=rows,
        shop=_shop(),
        footer_note="Numbers reflect repair orders in the selected date range. Active = open / in_progress / on_hold.",
        align_right=[1, 2, 3, 4],
    )
    fn = f"Production_Summary_{datetime.now().strftime('%Y%m%d')}.pdf"
    return _pdf_response(buf, fn)


@router.get("/ar-aging/pdf")
def ar_aging_pdf():
    rows_data = service.ar_aging()

    # Aggregate into aging buckets for the summary strip
    buckets = {"0-30 days": 0.0, "31-60 days": 0.0, "61-90 days": 0.0, "90+ days": 0.0}
    for r in rows_data:
        d = r.get("days_old") or 0
        b = "0-30 days" if d <= 30 else "31-60 days" if d <= 60 else "61-90 days" if d <= 90 else "90+ days"
        buckets[b] += float(r.get("balance_due") or 0)

    total_outstanding = sum(buckets.values())
    summary_stats = [
        ("Total Outstanding", _money(total_outstanding)),
        ("0-30 Days",         _money(buckets["0-30 days"])),
        ("31-60 Days",        _money(buckets["31-60 days"])),
        ("61-90 Days",        _money(buckets["61-90 days"])),
        ("90+ Days",          _money(buckets["90+ days"])),
        ("Open Invoices",     str(len(rows_data))),
    ]

    headers = ["RO #", "Customer", "Insurance", "Total", "Paid", "Balance", "Days Old"]
    rows = []
    for r in rows_data:
        rows.append([
            r.get("ro_number") or "—",
            _cust_name(r),
            r.get("insurance_name") or "—",
            _money(r.get("total_amount")),
            _money(r.get("amount_paid")),
            _money(r.get("balance_due")),
            str(r.get("days_old") or 0),
        ])

    buf = generate_report_pdf(
        title="AR Aging",
        subtitle=f"As of {datetime.now().strftime('%B %d, %Y')} — sorted oldest first",
        summary_stats=summary_stats,
        headers=headers,
        rows=rows,
        shop=_shop(),
        landscape_mode=True,
        align_right=[3, 4, 5, 6],
        footer_note="Only repair orders with an outstanding balance are included.",
    )
    fn = f"AR_Aging_{datetime.now().strftime('%Y%m%d')}.pdf"
    return _pdf_response(buf, fn)


@router.get("/employee-productivity/pdf")
def employee_productivity_pdf():
    rows_data = service.employee_productivity()

    headers = ["Code", "Name", "Role", "Total Hours", "ROs Worked"]
    rows = []
    for r in rows_data:
        rows.append([
            r.get("employee_code") or "—",
            f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
            (r.get("role") or "").title(),
            f"{float(r.get('total_hours') or 0):.2f}",
            str(r.get("ros_worked") or 0),
        ])

    total_hours = sum(float(r.get("total_hours") or 0) for r in rows_data)
    summary_stats = [
        ("Active Employees", str(len(rows_data))),
        ("Total Hours",      f"{total_hours:.1f}"),
    ]

    buf = generate_report_pdf(
        title="Employee Productivity",
        subtitle=f"As of {datetime.now().strftime('%B %d, %Y')}",
        summary_stats=summary_stats,
        headers=headers,
        rows=rows,
        shop=_shop(),
        align_right=[3, 4],
        footer_note="Hours totaled from time cards. ROs Worked counts each repair order the employee was assigned to.",
    )
    fn = f"Employee_Productivity_{datetime.now().strftime('%Y%m%d')}.pdf"
    return _pdf_response(buf, fn)


@router.get("/parts-summary/pdf")
def parts_summary_pdf():
    rows_data = service.parts_summary()

    total_price = sum(float(r.get("total_price") or 0) for r in rows_data)
    total_cost  = sum(float(r.get("total_cost")  or 0) for r in rows_data)
    total_profit = total_price - total_cost
    margin = (total_profit / total_price * 100) if total_price else 0.0

    summary_stats = [
        ("Line Items",        str(len(rows_data))),
        ("Total Sold",        _money(total_price)),
        ("Total Cost",        _money(total_cost)),
        ("Gross Profit",      f"{_money(total_profit)} ({margin:.1f}%)"),
    ]

    headers = ["Part #", "Description", "Type", "Qty", "Price", "Cost", "Profit"]
    rows = []
    for r in rows_data:
        rows.append([
            r.get("part_number") or "—",
            (r.get("description") or "")[:60],
            (r.get("part_type") or "—").title(),
            f"{float(r.get('total_qty') or 0):.0f}",
            _money(r.get("total_price")),
            _money(r.get("total_cost")),
            _money(r.get("profit")),
        ])

    buf = generate_report_pdf(
        title="Parts Summary",
        subtitle="Roll-up of every part billed on a repair order",
        summary_stats=summary_stats,
        headers=headers,
        rows=rows,
        shop=_shop(),
        landscape_mode=True,
        align_right=[3, 4, 5, 6],
        footer_note="Top 500 parts by revenue. Same part billed on multiple ROs is aggregated.",
    )
    fn = f"Parts_Summary_{datetime.now().strftime('%Y%m%d')}.pdf"
    return _pdf_response(buf, fn)


@router.get("/cycle-time/pdf")
def cycle_time_pdf():
    c = service.cycle_time()
    fmt_days = lambda v: f"{float(v):.1f} days" if v is not None else "—"

    summary_stats = [
        ("Completed ROs",       str(c.get("total_completed") or 0)),
        ("Avg. Days to Complete", fmt_days(c.get("avg_days_to_complete"))),
        ("Fastest",             fmt_days(c.get("min_days"))),
        ("Slowest",             fmt_days(c.get("max_days"))),
    ]

    buf = generate_report_pdf(
        title="Cycle Time Analysis",
        subtitle=f"As of {datetime.now().strftime('%B %d, %Y')}",
        summary_stats=summary_stats,
        headers=None,
        rows=None,
        shop=_shop(),
        footer_note="Cycle time measured from RO creation to actual completion date "
                    "(falls back to last update if completion date is missing).",
    )
    fn = f"Cycle_Time_{datetime.now().strftime('%Y%m%d')}.pdf"
    return _pdf_response(buf, fn)
