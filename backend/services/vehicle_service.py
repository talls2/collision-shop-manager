"""
VehicleService: Business logic for vehicle management.
Encapsulates validation and delegates data access to VehicleRepository.
"""
from repositories.vehicle_repository import VehicleRepository


class VehicleService:
    """Service for managing vehicles with validation."""

    def __init__(self):
        self.repo = VehicleRepository()

    def list_vehicles(self, search: str | None = None, customer_id: int | None = None) -> list[dict]:
        """
        List all vehicles, optionally filtered by search term or customer.

        Args:
            search: Search term to filter vehicles by VIN, make, model, license plate, or customer name
            customer_id: Filter by owner customer ID

        Returns:
            List of vehicle dictionaries
        """
        if customer_id:
            return self.repo.get_by_customer(customer_id)
        if search:
            return self.repo.search_vehicles(search)
        return self.repo.get_all()

    def get_vehicle(self, vehicle_id: int) -> dict | None:
        """
        Get a vehicle by ID with owner (customer) information.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            Vehicle dictionary with customer info or None if not found
        """
        return self.repo.get_with_owner(vehicle_id)

    def get_by_customer(self, customer_id: int) -> list[dict]:
        """
        Get all vehicles owned by a customer.

        Args:
            customer_id: Customer ID

        Returns:
            List of vehicle dictionaries for that customer
        """
        return self.repo.get_by_customer(customer_id)

    def create_vehicle(self, data: dict) -> int:
        """
        Create a new vehicle.

        Args:
            data: Vehicle data dict

        Returns:
            New vehicle ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not data.get("customer_id"):
            raise ValueError("Vehicle must have a customer_id")

        return self.repo.insert(data)

    def update_vehicle(self, vehicle_id: int, data: dict) -> None:
        """
        Update an existing vehicle.

        Args:
            vehicle_id: Vehicle ID
            data: Updated vehicle data

        Raises:
            ValueError: If vehicle not found
        """
        existing = self.repo.get_by_id(vehicle_id)
        if not existing:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        self.repo.update(vehicle_id, data)
