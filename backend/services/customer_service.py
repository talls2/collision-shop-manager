"""
CustomerService: Business logic for customer management.
Encapsulates validation and delegates data access to CustomerRepository.
"""
from repositories.customer_repository import CustomerRepository


class CustomerService:
    """Service for managing customers with validation."""

    def __init__(self):
        self.repo = CustomerRepository()

    def list_customers(self, search: str | None = None) -> list[dict]:
        """
        List all customers, optionally filtered by search term.

        Args:
            search: Search term to filter customers

        Returns:
            List of customer dictionaries
        """
        if search:
            return self.repo.search_customers(search)
        return self.repo.get_all()

    def get_customer(self, customer_id: int) -> dict | None:
        """
        Get a customer by ID with all related data (vehicles, estimates, repair orders).

        Args:
            customer_id: Customer ID

        Returns:
            Customer dictionary with relations or None if not found
        """
        return self.repo.get_with_relations(customer_id)

    def create_customer(self, data: dict) -> int:
        """
        Create a new customer with validation.

        Args:
            data: Customer data dict. Must contain:
                - For individuals: first_name, last_name
                - For companies: company_name, first_name, last_name

        Returns:
            New customer ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        customer_type = data.get("customer_type", "individual")

        if customer_type == "individual":
            if not data.get("first_name"):
                raise ValueError("Individual customers require first_name")
            if not data.get("last_name"):
                raise ValueError("Individual customers require last_name")
        elif customer_type == "company":
            if not data.get("company_name"):
                raise ValueError("Company customers require company_name")

        return self.repo.insert(data)

    def update_customer(self, customer_id: int, data: dict) -> None:
        """
        Update an existing customer with validation.

        Args:
            customer_id: Customer ID
            data: Updated customer data

        Raises:
            ValueError: If validation fails
        """
        # Get existing customer to validate
        existing = self.repo.get_by_id(customer_id)
        if not existing:
            raise ValueError(f"Customer {customer_id} not found")

        # Merge and validate
        merged = {**existing, **data}
        customer_type = merged.get("customer_type", "individual")

        if customer_type == "individual":
            if not merged.get("first_name"):
                raise ValueError("Individual customers require first_name")
            if not merged.get("last_name"):
                raise ValueError("Individual customers require last_name")
        elif customer_type == "company":
            if not merged.get("company_name"):
                raise ValueError("Company customers require company_name")

        self.repo.update(customer_id, data)
