"""
ProductionService: Business logic for production schedule management.
"""
from repositories.production_repository import ProductionRepository
from repositories.repair_order_repository import RepairOrderRepository


class ProductionService:
    """Service for managing production schedule entries."""

    def __init__(self):
        self.repo = ProductionRepository()
        self.ro_repo = RepairOrderRepository()

    def list_schedule(self, status: str | None = None,
                      department: str | None = None) -> list[dict]:
        """List production schedule entries with optional filtering."""
        return self.repo.list_with_details(status=status, department=department)

    def get_by_ro(self, ro_id: int) -> list[dict]:
        """Get all production schedule entries for a repair order."""
        return self.repo.get_by_ro(ro_id)

    def create_entry(self, data: dict) -> int:
        """
        Create a new production schedule entry.

        Args:
            data: Schedule data (ro_id required, department, scheduled_date, etc.)

        Returns:
            New schedule entry ID

        Raises:
            ValueError: If validation fails
        """
        if not data.get("ro_id"):
            raise ValueError("Production entry must have an ro_id")

        # Verify RO exists
        ro = self.ro_repo.get_by_id(data["ro_id"])
        if not ro:
            raise ValueError(f"Repair order {data['ro_id']} not found")

        if "status" not in data:
            data["status"] = "scheduled"

        return self.repo.insert(data)

    def update_entry(self, entry_id: int, data: dict) -> None:
        """Update a production schedule entry."""
        existing = self.repo.get_by_id(entry_id)
        if not existing:
            raise ValueError(f"Production entry {entry_id} not found")

        self.repo.update(entry_id, data)

    def update_status(self, entry_id: int, new_status: str) -> None:
        """Update the status of a production entry."""
        existing = self.repo.get_by_id(entry_id)
        if not existing:
            raise ValueError(f"Production entry {entry_id} not found")

        self.repo.update(entry_id, {"status": new_status})
