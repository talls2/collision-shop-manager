"""
PaymentRepository: Payment CRUD for repair orders.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class PaymentRepository(BaseRepository):
    table_name = "payments"
    order_by = "payment_date DESC"

    def get_by_ro(self, ro_id: int, limit: int = 500) -> list[dict]:
        """
        Get all payments for a repair order, ordered by payment_date DESC.
        """
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE ro_id = ?
                ORDER BY {self.order_by}
                LIMIT ?
                """,
                (ro_id, limit)
            ).fetchall()
        return rows_to_list(rows)

    def add_payment(self, ro_id: int, data: dict) -> int:
        """
        Add a payment to a repair order.
        Returns the payment id.
        """
        with get_db() as db:
            cols = ["ro_id"] + list(data.keys())
            vals = [ro_id] + list(data.values())
            placeholders = ", ".join(["?"] * len(cols))
            col_str = ", ".join(cols)

            cur = db.execute(
                f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders})",
                vals
            )
            db.commit()
            return cur.lastrowid

    def get_payment(self, payment_id: int) -> dict | None:
        """Return a single payment row, or None if it doesn't exist."""
        with get_db() as db:
            row = db.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (payment_id,)
            ).fetchone()
        return row_to_dict(row) if row else None

    def delete_payment(self, payment_id: int) -> bool:
        """
        Void (hard-delete) a payment by id. Returns True if a row was deleted.
        The caller is responsible for recalculating the RO's amount_paid /
        balance_due after this returns.
        """
        with get_db() as db:
            cur = db.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?",
                (payment_id,)
            )
            db.commit()
            return cur.rowcount > 0
