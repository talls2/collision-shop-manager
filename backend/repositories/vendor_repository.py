"""
VendorRepository: Vendor CRUD and search.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class VendorRepository(BaseRepository):
    table_name = "vendors"
    order_by = "vendor_name"

    def search_vendors(self, term: str, limit: int = 100) -> list[dict]:
        """
        Search vendors by vendor_name, contact_name, email, phone.
        """
        search_term = f"%{term}%"
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE vendor_name LIKE ? OR contact_name LIKE ?
                   OR email LIKE ? OR phone LIKE ?
                ORDER BY {self.order_by}
                LIMIT ?
                """,
                (search_term, search_term, search_term, search_term, limit)
            ).fetchall()
        return rows_to_list(rows)
