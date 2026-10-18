"""
EmployeeRepository: Employee CRUD with activity history.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class EmployeeRepository(BaseRepository):
    table_name = "employees"
    order_by = "last_name"

    def list_active(self, limit: int = 500) -> list[dict]:
        """
        Get all active employees (is_active = 1).
        """
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE is_active = 1
                ORDER BY {self.order_by}
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
        return rows_to_list(rows)

    def get_with_history(self, eid: int) -> dict | None:
        """
        Get employee with recent time_cards and recent flag_pay records.
        """
        with get_db() as db:
            # Get employee
            employee = db.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (eid,)
            ).fetchone()
            if not employee:
                return None

            employee = row_to_dict(employee)

            # Get recent time cards (last 50)
            time_cards = db.execute(
                """
                SELECT * FROM time_cards
                WHERE employee_id = ?
                ORDER BY clock_in DESC
                LIMIT 50
                """,
                (eid,)
            ).fetchall()
            employee["time_cards"] = rows_to_list(time_cards)

            # Get recent flag_pay records (last 20)
            flag_pays = db.execute(
                """
                SELECT * FROM flag_pay
                WHERE employee_id = ?
                ORDER BY date DESC
                LIMIT 20
                """,
                (eid,)
            ).fetchall()
            employee["flag_pay"] = rows_to_list(flag_pays)

        return employee
