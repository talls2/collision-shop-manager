"""
Base repository with common CRUD operations.
All entity repositories inherit from this.
"""
from config.database import get_db, row_to_dict, rows_to_list


class BaseRepository:
    """Generic repository providing standard CRUD for a single table."""

    table_name: str = ""
    order_by: str = "id DESC"

    def get_all(self, limit: int = 500) -> list[dict]:
        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM {self.table_name} ORDER BY {self.order_by} LIMIT ?",
                (limit,)
            ).fetchall()
        return rows_to_list(rows)

    def get_by_id(self, record_id: int) -> dict | None:
        with get_db() as db:
            row = db.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return row_to_dict(row)

    def insert(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        with get_db() as db:
            cur = db.execute(
                f"INSERT INTO {self.table_name} ({cols}) VALUES ({placeholders})",
                tuple(data.values())
            )
            db.commit()
            return cur.lastrowid

    def update(self, record_id: int, data: dict) -> None:
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        with get_db() as db:
            db.execute(
                f"UPDATE {self.table_name} SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                (*data.values(), record_id)
            )
            db.commit()

    def delete(self, record_id: int) -> None:
        with get_db() as db:
            db.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            db.commit()

    def search(self, columns: list[str], term: str, limit: int = 100) -> list[dict]:
        conditions = " OR ".join(f"{c} LIKE ?" for c in columns)
        params = [f"%{term}%"] * len(columns)
        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM {self.table_name} WHERE {conditions} ORDER BY {self.order_by} LIMIT ?",
                (*params, limit)
            ).fetchall()
        return rows_to_list(rows)

    def count(self, where: str = "1=1", params: tuple = ()) -> int:
        with get_db() as db:
            row = db.execute(
                f"SELECT COUNT(*) as c FROM {self.table_name} WHERE {where}", params
            ).fetchone()
        return row["c"]
