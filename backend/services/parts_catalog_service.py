"""
PartsCatalogService: a price book that grows as the estimator quotes parts.

Workflow:
  1. Estimator adds a part line to an estimate. The line has part_number + price.
  2. The frontend prompts: "Save this part to the catalog for next time?"
  3. On confirm, this service creates or updates the catalog row.
  4. On future part lines, the frontend autocompletes from the catalog and
     prefills description/price.
"""
from datetime import date
from config.database import get_db


class PartsCatalogService:
    """CRUD + lookup for the parts price catalog."""

    # ── Lookups ──
    def list_all(self, search: str | None = None, limit: int = 500) -> list[dict]:
        sql = """
            SELECT pc.*, v.vendor_name AS preferred_vendor_name
            FROM parts_catalog pc
            LEFT JOIN vendors v ON v.id = pc.preferred_vendor_id
        """
        params: list = []
        if search:
            sql += """ WHERE pc.part_number LIKE ? OR pc.description LIKE ? OR pc.vehicle_compat LIKE ?"""
            t = f"%{search}%"
            params.extend([t, t, t])
        sql += " ORDER BY pc.usage_count DESC, pc.part_number ASC LIMIT ?"
        params.append(limit)
        with get_db() as db:
            rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_by_part_number(self, part_number: str) -> dict | None:
        if not part_number:
            return None
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM parts_catalog WHERE part_number = ? COLLATE NOCASE",
                (part_number.strip(),),
            ).fetchone()
        return dict(row) if row else None

    # ── Mutations ──
    def upsert(self, data: dict) -> int:
        """
        Insert or update a catalog entry by part_number.
        Returns the catalog row id.
        """
        part_number = (data.get("part_number") or "").strip()
        if not part_number:
            raise ValueError("part_number is required")

        existing = self.get_by_part_number(part_number)
        today = date.today().isoformat()

        if existing:
            updates = {
                "description":         data.get("description") or existing.get("description"),
                "standard_price":      float(data.get("standard_price") or existing.get("standard_price") or 0),
                "standard_cost":       float(data.get("standard_cost") or existing.get("standard_cost") or 0),
                "part_type":           data.get("part_type") or existing.get("part_type"),
                "preferred_vendor_id": data.get("preferred_vendor_id") or existing.get("preferred_vendor_id"),
                "vehicle_compat":      data.get("vehicle_compat") or existing.get("vehicle_compat"),
                "notes":               data.get("notes") or existing.get("notes"),
                "usage_count":         (existing.get("usage_count") or 0) + 1,
                "last_used_date":      today,
            }
            with get_db() as db:
                set_clause = ", ".join(f"{k} = ?" for k in updates) + ", updated_at = datetime('now')"
                db.execute(
                    f"UPDATE parts_catalog SET {set_clause} WHERE id = ?",
                    (*updates.values(), existing["id"]),
                )
                db.commit()
            return existing["id"]

        # Insert
        row = {
            "part_number":         part_number,
            "description":         data.get("description"),
            "standard_price":      float(data.get("standard_price") or 0),
            "standard_cost":       float(data.get("standard_cost") or 0),
            "part_type":           data.get("part_type"),
            "preferred_vendor_id": data.get("preferred_vendor_id"),
            "vehicle_compat":      data.get("vehicle_compat"),
            "notes":               data.get("notes"),
            "usage_count":         1,
            "last_used_date":      today,
        }
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        with get_db() as db:
            cur = db.execute(
                f"INSERT INTO parts_catalog ({cols}) VALUES ({placeholders})",
                tuple(row.values()),
            )
            db.commit()
            return cur.lastrowid

    def update(self, catalog_id: int, data: dict) -> None:
        allowed = {"description", "standard_price", "standard_cost", "part_type",
                   "preferred_vendor_id", "vehicle_compat", "notes"}
        clean = {k: v for k, v in data.items() if k in allowed}
        if not clean:
            return
        set_clause = ", ".join(f"{k} = ?" for k in clean) + ", updated_at = datetime('now')"
        with get_db() as db:
            db.execute(
                f"UPDATE parts_catalog SET {set_clause} WHERE id = ?",
                (*clean.values(), catalog_id),
            )
            db.commit()

    def delete(self, catalog_id: int) -> None:
        with get_db() as db:
            db.execute("DELETE FROM parts_catalog WHERE id = ?", (catalog_id,))
            db.commit()
