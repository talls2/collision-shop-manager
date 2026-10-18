"""
ShopRepository: Shop info, rates, and templates management.
"""
from config.database import get_db, row_to_dict, rows_to_list


class ShopRepository:
    """Shop-level configuration and reference data."""

    def get_shop_info(self) -> dict | None:
        """
        Get shop information (body_shop table).
        Returns the first (and usually only) row.
        """
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM body_shop LIMIT 1"
            ).fetchone()
        return row_to_dict(row)

    def update_shop_info(self, data: dict) -> None:
        """
        Update shop information (upsert pattern).
        If a row exists, update it; otherwise insert.
        """
        with get_db() as db:
            # Check if row exists
            row = db.execute("SELECT id FROM body_shop LIMIT 1").fetchone()

            if row:
                # Update
                set_clause = ", ".join(f"{k} = ?" for k in data.keys())
                set_clause += ", updated_at = datetime('now')"
                db.execute(
                    f"UPDATE body_shop SET {set_clause} WHERE id = ?",
                    (*data.values(), row["id"])
                )
            else:
                # Insert
                cols = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                db.execute(
                    f"INSERT INTO body_shop ({cols}) VALUES ({placeholders})",
                    tuple(data.values())
                )
            db.commit()

    def get_rates(self) -> list[dict]:
        """
        Get all active shop rates (is_active = 1).
        """
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM shop_rates WHERE is_active = 1 ORDER BY rate_name"
            ).fetchall()
        return rows_to_list(rows)

    def get_templates(self) -> list[dict]:
        """
        Get all letter templates.
        """
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM letter_templates ORDER BY template_name"
            ).fetchall()
        return rows_to_list(rows)
