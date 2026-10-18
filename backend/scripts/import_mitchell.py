"""
Import Mitchell ABS7 XML + CSI text export into the shop_manager database.

Usage:
    python backend/scripts/import_mitchell.py <xml_path> [csi_path]

Environment:
    SHOP_DB_PATH - path to SQLite DB (defaults to backend/data/shop_manager.db)
    IMPORT_YEAR_FROM - only import ROs created on or after this year (default 2012)
    IMPORT_WIPE - set to 1 to wipe existing customers/vehicles/ROs before import

This script is idempotent: repeated runs produce the same final DB state (with wipe),
or skip already-imported records (without wipe, by matching on ro_number).
"""
import os
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))
from config.database import get_db, _ensure_data_dir  # noqa: E402
from config.schema import TABLES, INDEXES  # noqa: E402


# ── Config ────────────────────────────────────────────────
YEAR_FROM = int(os.environ.get("IMPORT_YEAR_FROM", "2012"))
WIPE = os.environ.get("IMPORT_WIPE", "0") == "1"


# ── XML helpers ────────────────────────────────────────────
def txt(el, path):
    """Safely get trimmed text from an XML path (returns '' if missing/empty)."""
    if el is None:
        return ""
    e = el.find(path)
    return (e.text or "").strip() if e is not None and e.text else ""


def to_int(s):
    try:
        return int(s) if s and s.strip() else None
    except (ValueError, TypeError):
        return None


def to_float(s):
    try:
        return float(s) if s and s.strip() else 0.0
    except (ValueError, TypeError):
        return 0.0


def clean_phone(s):
    """Keep digits and common phone formatting."""
    if not s:
        return None
    s = s.strip()
    return s if s and s != "0" else None


def norm(s):
    """Normalize blank/placeholder strings to None."""
    if s is None:
        return None
    s = s.strip()
    if not s or s in (".", "-", "--"):
        return None
    return s


def ro_year(ro_date):
    """Extract year from 'YYYY-MM-DD' style date."""
    if ro_date and len(ro_date) >= 4 and ro_date[:4].isdigit():
        return int(ro_date[:4])
    return None


# ── Load XML ──────────────────────────────────────────────
def load_xml(xml_path):
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    # Repair truncated root element if needed
    if not content.rstrip().endswith("</ABS7_REPAIR_ORDER>"):
        content = content.rstrip() + "\n</ABS7_REPAIR_ORDER>\n"
    root = ET.fromstring(content)
    return root.findall(".//REPAIR_ORDER")


# ── Load CSI (pipe-delimited text) ─────────────────────────
# Columns (from inspection):
# 0: shop, 1: RO#, 2-5: ?, 6: cust first, 7: cust last/company, 8: city, 9: state,
# 10: zip, 11: ?, 12: phone, 13: make, 14: model, 15: total, 16: ?, 17: date_start,
# 18: date_end, 19: salesperson, 20-22: ?, 23: email, 24: notes
def load_csi(csi_path):
    """Return dict keyed by (last_name_lower, city_lower) -> merged contact info."""
    merged = {}
    if not csi_path or not os.path.exists(csi_path):
        return merged
    with open(csi_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) < 20:
                continue
            first = norm(parts[6] if len(parts) > 6 else "")
            last = norm(parts[7] if len(parts) > 7 else "")
            city = norm(parts[8] if len(parts) > 8 else "")
            state = norm(parts[9] if len(parts) > 9 else "")
            zip_ = norm(parts[10] if len(parts) > 10 else "")
            phone = clean_phone(parts[12] if len(parts) > 12 else "")
            email = norm(parts[23] if len(parts) > 23 else "")
            salesperson = norm(parts[19] if len(parts) > 19 else "")
            if not last:
                continue
            key = last.lower()
            entry = merged.setdefault(key, {})
            for k, v in [("city", city), ("state", state), ("zip_code", zip_),
                         ("phone_work", phone), ("email", email), ("salesperson", salesperson),
                         ("first_name_hint", first)]:
                if v and not entry.get(k):
                    entry[k] = v
    return merged


# ── Import logic ──────────────────────────────────────────
def wipe_business_data(conn):
    """Remove customers/vehicles/estimates/ROs (keep shop, rates, employees, users)."""
    cur = conn.cursor()
    for tbl in ["ro_lines", "estimate_lines", "payments", "part_invoice_lines",
                "part_invoices", "time_cards", "flag_pay", "production_schedule",
                "vehicle_movements", "activity_log",
                "repair_orders", "estimates",
                "vehicles", "customers", "insurance_agents", "insurance_companies"]:
        try:
            cur.execute(f"DELETE FROM {tbl}")
        except Exception as e:
            print(f"  (skip {tbl}: {e})")
    # Reset autoincrement counters so new IDs start at 1
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN "
                "('customers','vehicles','repair_orders','estimates',"
                " 'insurance_companies','insurance_agents')")
    conn.commit()


def ensure_tables(conn):
    cur = conn.cursor()
    for stmt in TABLES:
        cur.execute(stmt)
    for stmt in INDEXES:
        cur.execute(stmt)
    conn.commit()


def import_ros(conn, ros, csi_map):
    cur = conn.cursor()

    # Track dedup: CUSTOMER_NUMBER -> customer_id
    cust_map = {}
    # Track dedup: VIN -> vehicle_id (only real VINs)
    vin_map = {}
    stats = {"customers": 0, "vehicles": 0, "ros": 0, "lines": 0, "skipped": 0}

    for ro in ros:
        header = ro.find("REPAIR_ORDER_HEADER")
        if header is None:
            continue

        # ── Filter by year ──
        ro_create = txt(header, "REPAIR_ORDER_CREATION_DATE")
        y = ro_year(ro_create)
        if y is None or y < YEAR_FROM:
            stats["skipped"] += 1
            continue

        # ── Customer ──
        cn = txt(header, "CUSTOMER/CUSTOMER_NUMBER")
        company = norm(txt(header, "CUSTOMER/COMPANY_NAME"))
        first = norm(txt(header, "CUSTOMER/FIRST_NAME"))
        last = norm(txt(header, "CUSTOMER/LAST_NAME"))
        addr = norm(txt(header, "CUSTOMER/ADDRESS_LINE_1"))
        city = norm(txt(header, "CUSTOMER/CITY"))
        state = norm(txt(header, "CUSTOMER/STATE"))
        zip_ = norm(txt(header, "CUSTOMER/ZIP"))
        home = clean_phone(txt(header, "CUSTOMER/HOME_PHONE"))
        work = clean_phone(txt(header, "CUSTOMER/WORK_PHONE"))
        email = norm(txt(header, "CUSTOMER/EMAIL"))

        # Merge in CSI enrichment
        if last:
            csi = csi_map.get(last.lower(), {})
            city = city or csi.get("city")
            state = state or csi.get("state")
            zip_ = zip_ or csi.get("zip_code")
            work = work or csi.get("phone_work")
            email = email or csi.get("email")

        if cn and cn in cust_map:
            customer_id = cust_map[cn]
        else:
            # Skip completely blank customers
            if not (company or first or last):
                stats["skipped"] += 1
                continue
            ctype = "company" if company else "individual"
            cur.execute("""INSERT INTO customers
                (customer_type, first_name, last_name, company_name,
                 address, city, state, zip_code, phone_home, phone_work, email)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ctype, first, last, company, addr, city, state, zip_, home, work, email))
            customer_id = cur.lastrowid
            if cn:
                cust_map[cn] = customer_id
            stats["customers"] += 1

        # ── Vehicle ──
        vyear = to_int(txt(header, "VEHICLE/YEAR"))
        vmake = norm(txt(header, "VEHICLE/MAKE"))
        vmodel = norm(txt(header, "VEHICLE/MODEL"))
        vvin = norm(txt(header, "VEHICLE/VIN"))
        vcolor = norm(txt(header, "VEHICLE/PRIMARY_COLOR"))
        vplate = norm(txt(header, "VEHICLE/LICENSE_NUMBER"))
        vstate = norm(txt(header, "VEHICLE/LICENSE_STATE"))
        vbody = norm(txt(header, "VEHICLE/BODY_STYLE"))

        vehicle_id = None
        if vvin and vvin in vin_map:
            vehicle_id = vin_map[vvin]
        elif vyear or vmake or vmodel or vvin:
            cur.execute("""INSERT INTO vehicles
                (customer_id, vin, year, make, model, submodel, color,
                 license_plate, license_state)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (customer_id, vvin, vyear, vmake, vmodel, vbody, vcolor, vplate, vstate))
            vehicle_id = cur.lastrowid
            if vvin:
                vin_map[vvin] = vehicle_id
            stats["vehicles"] += 1

        # ── Repair Order ──
        ro_num = txt(header, "REPAIR_ORDER_NUMBER") or txt(header, "ESTIMATE_NUMBER")
        if not ro_num:
            stats["skipped"] += 1
            continue

        # Suffix if collision; the RO# should be unique in Mitchell but just in case
        try_num = ro_num
        suffix = 1
        while cur.execute("SELECT 1 FROM repair_orders WHERE ro_number=?", (try_num,)).fetchone():
            try_num = f"{ro_num}-{suffix}"
            suffix += 1

        ro_total = to_float(txt(header, "REPAIR_ORDER_TOTAL"))
        ins_pays = to_float(txt(header, "INSURANCE_PAYS"))
        cust_pays = to_float(txt(header, "CUSTOMER_PAYS"))

        policy = norm(txt(header, "CLAIM_INFORMATION/POLICY_NUMBER"))
        claim = norm(txt(header, "CLAIM_INFORMATION/CLAIM_NUMBER"))
        loss = norm(txt(header, "CLAIM_INFORMATION/LOSS_DATE"))
        deductible = to_float(txt(header, "CLAIM_INFORMATION/DEDUCTIBLE_AMOUNT"))

        arrival = norm(txt(header, "REPAIR_ORDER_DATES/ACTUAL_ARRIVAL_DATE"))
        start = norm(txt(header, "REPAIR_ORDER_DATES/REPAIR_START_DATE"))
        completed = norm(txt(header, "REPAIR_ORDER_DATES/REPAIRS_COMPLETED"))
        delivered = norm(txt(header, "REPAIR_ORDER_DATES/CAR_DELIVERY_DATE"))
        closed_at = norm(txt(header, "REPAIR_ORDER_DATES/CLOSED_DATE"))

        amount_paid = ins_pays + cust_pays
        balance = max(0.0, ro_total - amount_paid) if ro_total else 0.0

        cur.execute("""INSERT INTO repair_orders
            (ro_number, customer_id, vehicle_id, policy_number, claim_number, deductible,
             status, loss_date, create_date, vehicle_arrived_date, repair_start_date,
             actual_complete_date, delivered_date, closed_date,
             total_amount, amount_paid, balance_due, notes)
            VALUES (?,?,?,?,?,?, 'closed', ?,?,?,?,?,?,?, ?,?,?,?)""",
            (try_num, customer_id, vehicle_id, policy, claim, deductible,
             loss, ro_create, arrival, start, completed, delivered, closed_at,
             ro_total, amount_paid, balance, None))
        ro_id = cur.lastrowid
        stats["ros"] += 1

        # ── Line Items (parts + labor — most historical ROs have none) ──
        line_n = 1
        for lbl in ro.findall(".//LABOR"):
            desc = norm(txt(lbl, "DAMAGE_DESCRIPTION")) or norm(txt(lbl, "LABOR_ACTION_CODE")) or "Labor"
            hours = to_float(txt(lbl, "LABOR_ALLOCATED_HOURS"))
            rate = to_float(txt(lbl, "HOURLY_RATE"))
            total = hours * rate
            cur.execute("""INSERT INTO ro_lines
                (ro_id, line_number, line_type, description, labor_hours, labor_rate, line_total, status)
                VALUES (?,?,?,?,?,?,?, 'complete')""",
                (ro_id, line_n, "labor", desc, hours, rate, total))
            line_n += 1
            stats["lines"] += 1

        for part in ro.findall(".//PART_LIST/*"):
            pn = norm(txt(part, "PART_NUMBER"))
            desc = norm(txt(part, "PART_DESCRIPTION")) or pn or "Part"
            qty = to_float(txt(part, "CUSTOMER_UNITS")) or 1.0
            price = to_float(txt(part, "PART_PRICE"))
            cost = to_float(txt(part, "PART_COST"))
            line_total = qty * price
            cur.execute("""INSERT INTO ro_lines
                (ro_id, line_number, line_type, description, part_number,
                 quantity, part_price, part_cost, line_total, status)
                VALUES (?,?,?,?,?,?,?,?,?, 'complete')""",
                (ro_id, line_n, "part", desc, pn, qty, price, cost, line_total))
            line_n += 1
            stats["lines"] += 1

    conn.commit()
    return stats


# ── Entry point ──────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python import_mitchell.py <xml_path> [csi_path]")
        sys.exit(1)
    xml_path = sys.argv[1]
    csi_path = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Loading XML from: {xml_path}")
    ros = load_xml(xml_path)
    print(f"  → Found {len(ros)} repair orders in XML")

    csi_map = load_csi(csi_path) if csi_path else {}
    if csi_map:
        print(f"Loaded CSI enrichment for {len(csi_map)} unique last-names from: {csi_path}")

    _ensure_data_dir()
    with get_db() as conn:
        ensure_tables(conn)
        if WIPE:
            print("Wiping existing business data (keeping shop/rates/employees/users)...")
            wipe_business_data(conn)

        print(f"Importing ROs from year {YEAR_FROM} onwards...")
        stats = import_ros(conn, ros, csi_map)

    print()
    print("=== Import complete ===")
    for k, v in stats.items():
        print(f"  {k:12s}: {v}")


if __name__ == "__main__":
    main()
