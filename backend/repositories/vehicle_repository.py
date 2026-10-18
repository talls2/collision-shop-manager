"""
VehicleRepository: Vehicle CRUD and queries with customer joins.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class VehicleRepository(BaseRepository):
    table_name = "vehicles"
    order_by = "year DESC"

    def search_vehicles(self, term: str, limit: int = 100) -> list[dict]:
        """
        Search vehicles by vin, make, model, license_plate plus customer names via JOIN.
        """
        search_term = f"%{term}%"
        with get_db() as db:
            rows = db.execute(
                """
                SELECT v.* FROM vehicles v
                LEFT JOIN customers c ON v.customer_id = c.id
                WHERE v.vin LIKE ? OR v.make LIKE ? OR v.model LIKE ?
                   OR v.license_plate LIKE ? OR c.first_name LIKE ? OR c.last_name LIKE ?
                ORDER BY v.year DESC
                LIMIT ?
                """,
                (search_term, search_term, search_term, search_term,
                 search_term, search_term, limit)
            ).fetchall()
        return rows_to_list(rows)

    def get_with_owner(self, vid: int) -> dict | None:
        """
        Get vehicle with customer info joined.
        """
        with get_db() as db:
            row = db.execute(
                """
                SELECT v.*, c.id as customer_id, c.first_name, c.last_name,
                       c.company_name, c.email, c.phone_home, c.phone_work
                FROM vehicles v
                LEFT JOIN customers c ON v.customer_id = c.id
                WHERE v.id = ?
                """,
                (vid,)
            ).fetchone()
        return row_to_dict(row)

    def get_by_customer(self, customer_id: int, limit: int = 500) -> list[dict]:
        """
        Get all vehicles for a customer.
        """
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE customer_id = ?
                ORDER BY {self.order_by}
                LIMIT ?
                """,
                (customer_id, limit)
            ).fetchall()
        return rows_to_list(rows)
