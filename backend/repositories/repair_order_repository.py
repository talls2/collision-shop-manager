"""
RepairOrderRepository: Repair Order CRUD with line items, payments, time cards, and totals.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository
from datetime import datetime


class RepairOrderRepository(BaseRepository):
    table_name = "repair_orders"
    order_by = "created_at DESC"

    def list_with_details(self, status=None, search=None, assigned_to=None, limit=500):
        query = """
            SELECT ro.*, c.first_name, c.last_name, c.company_name,
                   v.year AS vehicle_year, v.make AS vehicle_make,
                   v.model AS vehicle_model, v.vin, v.color AS vehicle_color
            FROM repair_orders ro
            LEFT JOIN customers c ON ro.customer_id = c.id
            LEFT JOIN vehicles v ON ro.vehicle_id = v.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND ro.status = ?"
            params.append(status)
        if search:
            t = f"%{search}%"
            query += """ AND (ro.ro_number LIKE ? OR c.first_name LIKE ?
                OR c.last_name LIKE ? OR c.company_name LIKE ?
                OR v.vin LIKE ? OR ro.claim_number LIKE ?)"""
            params.extend([t] * 6)
        if assigned_to:
            # Match the legacy worker columns OR a non-estimator ro_assignments row.
            # Estimators don't work on the vehicle so they're excluded from the
            # worker's "my jobs" view.
            query += """ AND (ro.technician_id = ? OR ro.painter_id = ?
                OR EXISTS (SELECT 1 FROM ro_assignments a
                           WHERE a.ro_id = ro.id AND a.employee_id = ?
                           AND LOWER(a.role) != 'estimator'))"""
            params.extend([assigned_to] * 3)
        query += f" ORDER BY ro.{self.order_by} LIMIT ?"
        params.append(limit)
        with get_db() as db:
            rows = db.execute(query, params).fetchall()
        return rows_to_list(rows)

    def get_full(self, rid):
        with get_db() as db:
            ro = db.execute("""
                SELECT ro.*,
                    c.first_name, c.last_name, c.company_name,
                    c.phone_home AS customer_phone, c.email AS customer_email,
                    c.address AS customer_address, c.city AS customer_city,
                    c.state AS customer_state, c.zip_code AS customer_zip,
                    c.billing_address, c.billing_city, c.billing_state, c.billing_zip,
                    v.year AS vehicle_year, v.make AS vehicle_make,
                    v.model AS vehicle_model, v.vin, v.color AS vehicle_color,
                    v.mileage, v.license_plate,
                    v.vehicle_type, v.engine_hours, v.length_feet, v.axle_count,
                    ic.company_name AS insurance_name, ic.phone AS insurance_phone,
                    est.first_name AS estimator_first, est.last_name AS estimator_last,
                    tech.first_name AS tech_first, tech.last_name AS tech_last,
                    ptr.first_name AS painter_first, ptr.last_name AS painter_last,
                    e.total_amount AS original_estimate_total,
                    e.estimate_number AS original_estimate_number
                FROM repair_orders ro
                LEFT JOIN customers c ON ro.customer_id = c.id
                LEFT JOIN vehicles v ON ro.vehicle_id = v.id
                LEFT JOIN insurance_companies ic ON ro.insurance_company_id = ic.id
                LEFT JOIN employees est ON ro.estimator_id = est.id
                LEFT JOIN employees tech ON ro.technician_id = tech.id
                LEFT JOIN employees ptr ON ro.painter_id = ptr.id
                LEFT JOIN estimates e ON ro.estimate_id = e.id
                WHERE ro.id = ?
            """, (rid,)).fetchone()
            if not ro:
                return None

            result = row_to_dict(ro)

            # Lines with vendor and tech names
            result['lines'] = rows_to_list(db.execute("""
                SELECT rl.*, v.vendor_name,
                    e.first_name AS tech_first, e.last_name AS tech_last
                FROM ro_lines rl
                LEFT JOIN vendors v ON rl.vendor_id = v.id
                LEFT JOIN employees e ON rl.assigned_tech_id = e.id
                WHERE rl.ro_id = ?
                ORDER BY rl.line_number
            """, (rid,)).fetchall())

            # Payments
            result['payments'] = rows_to_list(db.execute(
                "SELECT * FROM payments WHERE ro_id = ? ORDER BY payment_date DESC",
                (rid,)
            ).fetchall())

            # Time cards
            result['time_cards'] = rows_to_list(db.execute("""
                SELECT tc.*, e.first_name, e.last_name
                FROM time_cards tc
                LEFT JOIN employees e ON tc.employee_id = e.id
                WHERE tc.ro_id = ?
                ORDER BY tc.clock_in DESC
            """, (rid,)).fetchall())

            # Production schedule
            result['production'] = rows_to_list(db.execute("""
                SELECT ps.*, e.first_name AS tech_first, e.last_name AS tech_last
                FROM production_schedule ps
                LEFT JOIN employees e ON ps.assigned_tech_id = e.id
                WHERE ps.ro_id = ?
                ORDER BY ps.scheduled_date
            """, (rid,)).fetchall())

        return result

    def get_lines(self, rid):
        with get_db() as db:
            rows = db.execute("""
                SELECT rl.*, v.vendor_name,
                    e.first_name AS tech_first, e.last_name AS tech_last
                FROM ro_lines rl
                LEFT JOIN vendors v ON rl.vendor_id = v.id
                LEFT JOIN employees e ON rl.assigned_tech_id = e.id
                WHERE rl.ro_id = ?
                ORDER BY rl.line_number
            """, (rid,)).fetchall()
        return rows_to_list(rows)

    def add_line(self, rid, data):
        with get_db() as db:
            row = db.execute(
                "SELECT MAX(line_number) AS m FROM ro_lines WHERE ro_id = ?", (rid,)
            ).fetchone()
            next_line = (row['m'] or 0) + 1

            # Calculate line total
            lh = float(data.get('labor_hours', 0))
            lr = float(data.get('labor_rate', 0))
            ph = float(data.get('paint_hours', 0))
            pr = float(data.get('paint_rate', 0))
            pp = float(data.get('part_price', 0))
            qty = float(data.get('quantity', 1))
            line_total = (lh * lr) + (ph * pr) + (pp * qty)

            data['ro_id'] = rid
            data['line_number'] = next_line
            data['line_total'] = round(line_total, 2)

            cols = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur = db.execute(
                f"INSERT INTO ro_lines ({cols}) VALUES ({placeholders})",
                tuple(data.values())
            )
            db.commit()
            return cur.lastrowid

    def recalc_totals(self, rid):
        with get_db() as db:
            lines = db.execute("SELECT * FROM ro_lines WHERE ro_id = ?", (rid,)).fetchall()

            ro = db.execute(
                "SELECT tax_exempt FROM repair_orders WHERE id = ?", (rid,)
            ).fetchone()
            tax_exempt = bool(ro and ro["tax_exempt"])

            rate_row = db.execute(
                "SELECT rate_amount FROM shop_rates WHERE rate_type = 'sales_tax_rate' LIMIT 1"
            ).fetchone()
            tax_rate = (float(rate_row["rate_amount"]) / 100.0) if rate_row else 0.0625

            def line_amount(r):
                lt = r["line_type"]
                if lt == "labor":
                    return float(r["labor_hours"] or 0) * float(r["labor_rate"] or 0)
                if lt == "paint":
                    return float(r["paint_hours"] or 0) * float(r["paint_rate"] or 0)
                if lt == "part":
                    return float(r["part_price"] or 0) * float(r["quantity"] or 1)
                return float(r["line_total"] or 0)

            labor = sum(line_amount(r) for r in lines if r["line_type"] == "labor")
            parts = sum(line_amount(r) for r in lines if r["line_type"] == "part")
            paint = sum(line_amount(r) for r in lines if r["line_type"] == "paint")
            sublet = sum(line_amount(r) for r in lines if r["line_type"] == "sublet")
            other = sum(line_amount(r) for r in lines if r["line_type"] == "other")

            if tax_exempt:
                tax = 0.0
            else:
                taxable_total = sum(line_amount(r) for r in lines if r["taxable"])
                tax = taxable_total * tax_rate

            total = labor + parts + paint + sublet + other + tax

            paid_row = db.execute(
                "SELECT COALESCE(SUM(amount), 0) AS p FROM payments WHERE ro_id = ?", (rid,)
            ).fetchone()
            paid = float(paid_row['p'])
            balance = total - paid

            db.execute("""
                UPDATE repair_orders SET
                    subtotal_labor = ?, subtotal_parts = ?, subtotal_paint = ?,
                    subtotal_sublet = ?, subtotal_other = ?,
                    tax_amount = ?, total_amount = ?,
                    amount_paid = ?, balance_due = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (round(labor, 2), round(parts, 2), round(paint, 2),
                  round(sublet, 2), round(other, 2), round(tax, 2),
                  round(total, 2), round(paid, 2), round(balance, 2), rid))
            db.commit()

    def next_number(self):
        with get_db() as db:
            year = datetime.now().year
            row = db.execute(
                "SELECT ro_number FROM repair_orders ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row and row['ro_number']:
                try:
                    seq = int(row['ro_number'].split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            return f"RO-{year}-{seq:03d}"
