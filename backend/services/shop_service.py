"""
ShopService: Business logic for shop configuration and reference data.
Encapsulates shop info, rates, and templates management.
Delegates data access to ShopRepository.
"""
from repositories.shop_repository import ShopRepository


class ShopService:
    """Service for managing shop configuration and reference data."""

    def __init__(self):
        self.repo = ShopRepository()

    def get_info(self) -> dict | None:
        """
        Get shop information (name, address, phone, etc.).

        Returns:
            Shop info dictionary or None if not configured
        """
        return self.repo.get_shop_info()

    def update_info(self, data: dict) -> None:
        """
        Update shop information.

        Args:
            data: Shop info fields to update
        """
        self.repo.update_shop_info(data)

    def get_rates(self) -> list[dict]:
        """
        Get all active shop rates (labor rates, etc.).

        Returns:
            List of rate dictionaries
        """
        return self.repo.get_rates()

    def create_rate(self, data: dict) -> int:
        """
        Create a new shop rate (labor type, materials, tax rate, etc.).

        Args:
            data: rate dict with rate_name, rate_type, rate_amount.

        Returns:
            New rate ID.
        """
        if not data.get("rate_name"):
            raise ValueError("Rate name is required")
        if data.get("rate_amount") is None:
            raise ValueError("Rate amount is required")
        # rate_type slug — default to a sanitized form of the name if not given.
        if not data.get("rate_type"):
            data["rate_type"] = data["rate_name"].lower().replace(" ", "_").replace("/", "_")
        from config.database import get_db
        with get_db() as db:
            cur = db.execute(
                "INSERT INTO shop_rates (rate_name, rate_type, rate_amount) VALUES (?,?,?)",
                (data["rate_name"], data["rate_type"], float(data["rate_amount"])),
            )
            db.commit()
            return cur.lastrowid

    def update_rate(self, rate_id: int, data: dict) -> None:
        """Update fields on a shop rate."""
        from config.database import get_db
        sets = []
        vals = []
        for k in ("rate_name", "rate_type", "rate_amount"):
            if k in data and data[k] is not None:
                sets.append(f"{k} = ?")
                vals.append(float(data[k]) if k == "rate_amount" else data[k])
        if not sets:
            return
        vals.append(rate_id)
        with get_db() as db:
            db.execute(f"UPDATE shop_rates SET {', '.join(sets)} WHERE id = ?", vals)
            db.commit()

    def delete_rate(self, rate_id: int) -> None:
        """Delete a shop rate."""
        from config.database import get_db
        with get_db() as db:
            db.execute("DELETE FROM shop_rates WHERE id = ?", (rate_id,))
            db.commit()

    def get_templates(self) -> list[dict]:
        """
        Get all letter templates for correspondence.

        Returns:
            List of template dictionaries
        """
        return self.repo.get_templates()
