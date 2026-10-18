"""
ProductionRepository: Production schedule CRUD and queries.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class ProductionRepository(BaseRepository):
    table_name = "production_schedule"
    order_by = "scheduled_date ASC"

    def list_with_details(self, status: str | None = None,
                          department: str | None = None) -> list[dict]:
        """
        List production schedule entries with RO, customer, and vehicle info joined.
        Optionally filter by status and/or department.
        """
        query = """
            SELECT ps.*,
                   ro.ro_number,
                   c.first_name AS customer_first, c.last_name AS customer_last,
                   c.company_name,
                   v.year, v.make, v.model, v.color,
                   e.first_name AS tech_first, e.last_name AS tech_last
            FROM production_schedule ps
            LEFT JOIN repair_orders ro ON ps.ro_id = ro.id
            LEFT JOIN customers c ON ro.customer_id = c.id
            LEFT JOIN vehicles v ON ro.vehicle_id = v.id
            LEFT JOIN employees e ON ps.assigned_tech_id = e.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND ps.status = ?"
            params.append(status)

        if department:
            query += " AND ps.department = ?"
            params.append(department)

        query += f" ORDER BY {self.order_by}"

        with get_db() as db:
            rows = db.execute(query, params).fetchall()
        return rows_to_list(rows)

    def get_by_ro(self, ro_id: int) -> list[dict]:
        """Get all production schedule entries for a repair order."""
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT ps.*, e.first_name AS tech_first, e.last_name AS tech_last
                FROM {self.table_name} ps
                LEFT JOIN employees e ON ps.assigned_tech_id = e.id
                WHERE ps.ro_id = ?
                ORDER BY ps.scheduled_date ASC
                """,
                (ro_id,)
            ).fetchall()
        return rows_to_list(rows)
