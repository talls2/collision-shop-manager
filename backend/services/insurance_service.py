"""
InsuranceService: Business logic for insurance company management.
Encapsulates validation and delegates data access to InsuranceRepository.
"""
from repositories.insurance_repository import InsuranceRepository


class InsuranceService:
    """Service for managing insurance companies and agents."""

    def __init__(self):
        self.repo = InsuranceRepository()

    def list_insurance(self, search: str | None = None) -> list[dict]:
        """
        List all insurance companies, optionally filtered by search term.

        Args:
            search: Search term to filter by company name, contact, email, or phone

        Returns:
            List of insurance company dictionaries
        """
        if search:
            return self.repo.search_insurance(search)
        return self.repo.get_all()

    def get_insurance(self, insurance_id: int) -> dict | None:
        """
        Get an insurance company by ID with all its agents.

        Args:
            insurance_id: Insurance company ID

        Returns:
            Insurance company dictionary with agents list, or None if not found
        """
        return self.repo.get_with_agents(insurance_id)

    def create_insurance(self, data: dict) -> int:
        """
        Create a new insurance company.

        Args:
            data: Insurance company data dict

        Returns:
            New insurance company ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not data.get("company_name"):
            raise ValueError("Insurance company must have a company_name")

        return self.repo.insert(data)

    def update_insurance(self, insurance_id: int, data: dict) -> None:
        """
        Update an existing insurance company.

        Args:
            insurance_id: Insurance company ID
            data: Updated insurance company data

        Raises:
            ValueError: If insurance company not found
        """
        existing = self.repo.get_by_id(insurance_id)
        if not existing:
            raise ValueError(f"Insurance company {insurance_id} not found")

        self.repo.update(insurance_id, data)
