"""
EstimateRepository: Estimate CRUD with line items, totals calculation, and numbering.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository
from datetime import datetime


class EstimateRepository(BaseRepository):
    table_name = "estimates"
    order_by = "created_at DESC"

    def list_with_details(self, status=None, search=None, limit=500):
        query = """
            SELECT e.*, c.first_name, c.last_name, c.company_name,
                   v.year AS vehicle_year, v.make AS vehicle_make,
                   v.model AS vehicle_model, v.vin
            FROM estimates e
            LEFT JOIN customers c ON e.customer_id = c.id
            LEFT JOIN vehicles v ON e.vehicle_id = v.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND e.status = ?"
            params.append(status)
        if search:
            t = f"%{search}%"
            query += """ AND (e.estimate_number LIKE ? OR c.first_name LIKE ?
                OR c.last_name LIKE ? OR c.company_name LIKE ? OR v.vin LIKE ?)"""
            params.extend([t] * 5)
        query += f" ORDER BY e.{self.order_by} LIMIT ?"
        params.append(limit)
        with get_db() as db:
            rows = db.execute(query, params).fetchall()
        return rows_to_list(rows)

    def get_full(self, eid):
        with get_db() as db:
            est = db.execute("""
                SELECT e.*,
                    c.first_name, c.last_name, c.company_name,
                    c.phone_home AS customer_phone, c.email AS customer_email,
                    c.address AS customer_address, c.city AS customer_city,
                    c.state AS customer_state, c.zip_code AS customer_zip,
                    c.billing_address, c.billing_city, c.billing_state, c.billing_zip,
                    v.year AS vehicle_year, v.make AS vehicle_make,
                    v.model AS vehicle_model, v.vin, v.color AS vehicle_color, v.mileage,
                    v.vehicle_type, v.engine_hours, v.length_feet, v.axle_count,
                    ic.company_name AS insurance_name,
                    emp.first_name AS estimator_first, emp.last_name AS estimator_last
                FROM estimates e
                LEFT JOIN customers c ON e.customer_id = c.id
                LEFT JOIN vehicles v ON e.vehicle_id = v.id
                LEFT JOIN insurance_companies ic ON e.insurance_company_id = ic.id
                LEFT JOIN employees emp ON e.estimator_id = emp.id
                WHERE e.id = ?
            """, (eid,)).fetchone()
            if not est:
                return None

            result = row_to_dict(est)
            result['lines'] = rows_to_list(db.execute(
                "SELECT * FROM estimate_lines WHERE estimate_id = ? ORDER BY line_number",
                (eid,)
            ).fetchall())
        return result

    def get_lines(self, eid):
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM estimate_lines WHERE estimate_id = ? ORDER BY line_number",
                (eid,)
            ).fetchall()
        return rows_to_list(rows)

    def add_line(self, eid, data):
        with get_db() as db:
            row = db.execute(
                "SELECT MAX(line_number) AS m FROM estimate_lines WHERE estimate_id = ?",
                (eid,)
            ).fetchone()
            next_line = (row['m'] or 0) + 1

            lh = float(data.get('labor_hours', 0))
            lr = float(data.get('labor_rate', 0))
            ph = float(data.get('paint_hours', 0))
            pr = float(data.get('paint_rate', 0))
            pp = float(data.get('part_price', 0))
            qty = float(data.get('quantity', 1))
            line_total = (lh * lr) + (ph * pr) + (pp * qty)

            data['estimate_id'] = eid
            data['line_number'] = next_line
            data['line_total'] = round(line_total, 2)

            cols = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur = db.execute(
                f"INSERT INTO estimate_lines ({cols}) VALUES ({placeholders})",
                tuple(data.values())
            )
            db.commit()
            return cur.lastrowid

    def delete_line(self, eid, lid):
        with get_db() as db:
            db.execute(
                "DELETE FROM estimate_lines WHERE id = ? AND estimate_id = ?",
                (lid, eid)
            )
            db.commit()

    def recalc_totals(self, eid):
        with get_db() as db:
            lines = db.execute(
                "SELECT * FROM estimate_lines WHERE estimate_id = ?", (eid,)
            ).fetchall()

            est = db.execute(
                "SELECT tax_exempt FROM estimates WHERE id = ?", (eid,)
            ).fetchone()
            tax_exempt = bool(est and est["tax_exempt"])

            # Sales tax rate is configurable in shop_rates (percent value, e.g. 6.25)
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
                # sublet, other
                return float(r["line_total"] or 0)

            labor = sum(line_amount(r) for r in lines if r["line_type"] == "labor")
            parts = sum(line_amount(r) for r in lines if r["line_type"] == "part")
            paint = sum(line_amount(r) for r in lines if r["line_type"] == "paint")
            other = sum(line_amount(r) for r in lines if r["line_type"] in ("sublet", "other"))

            if tax_exempt:
                tax = 0.0
            else:
                taxable_total = sum(line_amount(r) for r in lines if r["taxable"])
                tax = taxable_total * tax_rate

            total = labor + parts + paint + other + tax

            db.execute("""
                UPDATE estimates SET
                    subtotal_labor = ?, subtotal_parts = ?,
                    subtotal_paint = ?, subtotal_other = ?,
                    tax_amount = ?, total_amount = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (round(labor, 2), round(parts, 2), round(paint, 2),
                  round(other, 2), round(tax, 2), round(total, 2), eid))
            db.commit()

    def next_number(self):
        with get_db() as db:
            year = datetime.now().year
            row = db.execute(
                "SELECT estimate_number FROM estimates ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row and row['estimate_number']:
                try:
                    seq = int(row['estimate_number'].split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            return f"EST-{year}-{seq:03d}"
