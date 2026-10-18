"""
ReportRepository: Analytical queries for shop reporting.

Return shapes match what the Reports UI expects. Each method takes
optional ISO date bounds where relevant.
"""
from config.database import get_db, rows_to_list, row_to_dict


class ReportRepository:
    """Shop reporting and analytics."""

    # ── Production Summary ────────────────────────────────────────
    def production_summary(self, start_date: str | None = None,
                           end_date: str | None = None) -> dict:
        """
        Production summary — one row of high-level numbers, plus the raw
        by-status breakdown for anyone who wants it.

        Frontend renders: active_ros, completed_ros, total_billed,
        total_collected, total_outstanding, total_labor, total_parts,
        total_paint.
        """
        where = "WHERE 1=1"
        params: list = []
        if start_date:
            where += " AND date(created_at) >= date(?)"
            params.append(start_date)
        if end_date:
            where += " AND date(created_at) <= date(?)"
            params.append(end_date)

        with get_db() as db:
            # Rolled-up numbers for the stat cards
            row = db.execute(
                f"""
                SELECT
                    SUM(CASE WHEN status IN ('open','in_progress','on_hold') THEN 1 ELSE 0 END) AS active_ros,
                    SUM(CASE WHEN status IN ('completed','closed','delivered') THEN 1 ELSE 0 END) AS completed_ros,
                    COALESCE(SUM(total_amount), 0)   AS total_billed,
                    COALESCE(SUM(amount_paid), 0)    AS total_collected,
                    COALESCE(SUM(balance_due), 0)    AS total_outstanding,
                    COALESCE(SUM(subtotal_labor), 0) AS total_labor,
                    COALESCE(SUM(subtotal_parts), 0) AS total_parts,
                    COALESCE(SUM(subtotal_paint), 0) AS total_paint,
                    COALESCE(SUM(tax_amount), 0)     AS total_tax,
                    COUNT(*)                          AS ro_count
                FROM repair_orders
                {where}
                """,
                params,
            ).fetchone()

            # By-status breakdown (used by the PDF and available in JSON)
            by_status = db.execute(
                f"""
                SELECT status, COUNT(*) AS count,
                       COALESCE(SUM(total_amount), 0) AS total_amount,
                       COALESCE(SUM(amount_paid), 0)  AS amount_paid,
                       COALESCE(SUM(balance_due), 0)  AS balance_due
                FROM repair_orders
                {where}
                GROUP BY status
                ORDER BY status
                """,
                params,
            ).fetchall()

            # Estimates in the same window
            est_rows = db.execute(
                f"""
                SELECT status, COUNT(*) AS count,
                       COALESCE(SUM(total_amount), 0) AS total_amount
                FROM estimates
                {where}
                GROUP BY status
                ORDER BY status
                """,
                params,
            ).fetchall()

        result = row_to_dict(row) or {}
        result["repair_orders_by_status"] = rows_to_list(by_status)
        result["estimates_by_status"] = rows_to_list(est_rows)
        result["date_range"] = {"start": start_date, "end": end_date}
        return result

    # ── AR Aging (per-RO list, with days_old) ────────────────────
    def ar_aging(self) -> list[dict]:
        """
        Per-repair-order accounts receivable list. Shows every RO with an
        outstanding balance, oldest first. Each row includes customer,
        insurance, and how old the balance is (days since created).
        """
        with get_db() as db:
            rows = db.execute(
                """
                SELECT
                    ro.id, ro.ro_number, ro.status,
                    ro.total_amount, ro.amount_paid, ro.balance_due,
                    ro.created_at,
                    CAST((julianday('now') - julianday(ro.created_at)) AS INTEGER) AS days_old,
                    c.first_name, c.last_name, c.company_name,
                    c.phone_home, c.phone_cell,
                    ic.company_name AS insurance_name
                FROM repair_orders ro
                LEFT JOIN customers c          ON ro.customer_id           = c.id
                LEFT JOIN insurance_companies ic ON ro.insurance_company_id = ic.id
                WHERE ro.balance_due > 0
                  AND ro.status != 'cancelled'
                ORDER BY days_old DESC
                """
            ).fetchall()
        return rows_to_list(rows)

    # ── Employee Productivity ────────────────────────────────────
    def employee_productivity(self) -> list[dict]:
        """
        Hours worked and ROs touched per employee. Total_hours is summed
        from every clock-in / clock-out pair on time_cards (labour and
        general clock-ins both count).
        """
        with get_db() as db:
            rows = db.execute(
                """
                SELECT
                    e.id, e.employee_code, e.first_name, e.last_name, e.role,
                    COALESCE(ROUND(SUM(
                        CASE
                            WHEN tc.clock_out IS NOT NULL AND tc.clock_in IS NOT NULL
                                THEN (julianday(tc.clock_out) - julianday(tc.clock_in)) * 24
                            ELSE 0
                        END
                    ), 2), 0) AS total_hours,
                    (
                        SELECT COUNT(DISTINCT ro.id)
                        FROM repair_orders ro
                        LEFT JOIN ro_assignments a ON a.ro_id = ro.id
                        WHERE (a.employee_id = e.id)
                           OR ro.technician_id = e.id
                           OR ro.painter_id    = e.id
                    ) AS ros_worked
                FROM employees e
                LEFT JOIN time_cards tc ON tc.employee_id = e.id
                WHERE e.is_active = 1
                GROUP BY e.id, e.employee_code, e.first_name, e.last_name, e.role
                ORDER BY total_hours DESC, e.last_name
                """
            ).fetchall()
        return rows_to_list(rows)

    # ── Parts Summary (per part number, rolled up) ───────────────
    def parts_summary(self) -> list[dict]:
        """
        Roll-up of parts sold across every repair order. Groups by
        part_number + description so the same part billed on multiple ROs
        aggregates into a single row.
        """
        with get_db() as db:
            rows = db.execute(
                """
                SELECT
                    COALESCE(NULLIF(TRIM(part_number), ''), '—') AS part_number,
                    description,
                    part_type,
                    SUM(quantity)                      AS total_qty,
                    SUM(quantity * part_price)         AS total_price,
                    SUM(quantity * part_cost)          AS total_cost,
                    SUM(quantity * (part_price - part_cost)) AS profit
                FROM ro_lines
                WHERE line_type = 'part'
                  AND (COALESCE(part_price, 0) > 0 OR COALESCE(part_cost, 0) > 0)
                GROUP BY COALESCE(NULLIF(TRIM(part_number), ''), '—'), description, part_type
                ORDER BY total_price DESC
                LIMIT 500
                """
            ).fetchall()
        return rows_to_list(rows)

    # ── Cycle Time ───────────────────────────────────────────────
    def cycle_time(self) -> dict:
        """
        How long completed ROs took from creation → completion (using
        actual_complete_date when present, otherwise updated_at).
        """
        with get_db() as db:
            row = db.execute(
                """
                SELECT
                    ROUND(AVG(days), 1) AS avg_days_to_complete,
                    MIN(days)           AS min_days,
                    MAX(days)           AS max_days,
                    COUNT(*)            AS total_completed
                FROM (
                    SELECT
                        CAST((julianday(COALESCE(actual_complete_date, updated_at))
                              - julianday(created_at)) AS REAL) AS days
                    FROM repair_orders
                    WHERE status IN ('completed', 'closed', 'delivered')
                      AND created_at IS NOT NULL
                )
                """
            ).fetchone()

        d = row_to_dict(row) or {}
        return {
            "avg_days_to_complete": d.get("avg_days_to_complete"),
            "min_days": d.get("min_days"),
            "max_days": d.get("max_days"),
            "total_completed": d.get("total_completed") or 0,
        }
