"""
CustomerRepository: Customer CRUD and queries with relation lookups.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class CustomerRepository(BaseRepository):
    table_name = "customers"
    order_by = "last_name, first_name"

    def search_customers(self, term: str, limit: int = 100) -> list[dict]:
        """
        Search customers by first_name, last_name, company_name, email, phone_home.
        """
        search_term = f"%{term}%"
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE first_name LIKE ? OR last_name LIKE ? OR company_name LIKE ?
                   OR email LIKE ? OR phone_home LIKE ?
                ORDER BY {self.order_by}
                LIMIT ?
                """,
                (search_term, search_term, search_term, search_term, search_term, limit)
            ).fetchall()
        return rows_to_list(rows)

    def get_with_relations(self, cid: int) -> dict | None:
        """
        Get customer with all related vehicles, estimates, and repair_orders via JOINs.
        Returns customer dict with nested lists.
        """
        with get_db() as db:
            # Get customer
            customer = db.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (cid,)
            ).fetchone()
            if not customer:
                return None

            customer = row_to_dict(customer)

            # Get vehicles
            vehicles = db.execute(
                "SELECT v.* FROM vehicles v WHERE v.customer_id = ? ORDER BY v.year DESC",
                (cid,)
            ).fetchall()
            customer["vehicles"] = rows_to_list(vehicles)

            # Get estimates
            estimates = db.execute(
                """
                SELECT e.* FROM estimates e
                WHERE e.customer_id = ?
                ORDER BY e.created_at DESC
                """,
                (cid,)
            ).fetchall()
            customer["estimates"] = rows_to_list(estimates)

            # Get repair orders
            repair_orders = db.execute(
                """
                SELECT ro.* FROM repair_orders ro
                WHERE ro.customer_id = ?
                ORDER BY ro.created_at DESC
                """,
                (cid,)
            ).fetchall()
            customer["repair_orders"] = rows_to_list(repair_orders)

        return customer
