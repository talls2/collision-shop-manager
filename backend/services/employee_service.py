"""
EmployeeService: Business logic for employee management.
Encapsulates validation and delegates data access to EmployeeRepository.
"""
from repositories.employee_repository import EmployeeRepository
from config.database import get_db


class EmployeeService:
    """Service for managing employees."""

    def __init__(self):
        self.repo = EmployeeRepository()

    def list_employees(self, active_only: bool = True) -> list[dict]:
        """
        List employees, optionally filtered to active only.

        Args:
            active_only: If True, return only active employees (is_active = 1)

        Returns:
            List of employee dictionaries
        """
        if active_only:
            return self.repo.list_active()
        return self.repo.get_all()

    def get_employee(self, employee_id: int) -> dict | None:
        """
        Get an employee by ID with history (time cards and flag pay records).

        Args:
            employee_id: Employee ID

        Returns:
            Employee dictionary with time_cards and flag_pay lists, or None if not found
        """
        return self.repo.get_with_history(employee_id)

    def create_employee(self, data: dict) -> int:
        """
        Create a new employee.

        Args:
            data: Employee data dict

        Returns:
            New employee ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not data.get("first_name"):
            raise ValueError("Employee must have first_name")
        if not data.get("last_name"):
            raise ValueError("Employee must have last_name")

        # Set default is_active if not provided
        if "is_active" not in data:
            data["is_active"] = 1

        return self.repo.insert(data)

    def update_employee(self, employee_id: int, data: dict) -> None:
        """
        Update an existing employee.

        Args:
            employee_id: Employee ID
            data: Updated employee data

        Raises:
            ValueError: If employee not found
        """
        existing = self.repo.get_by_id(employee_id)
        if not existing:
            raise ValueError(f"Employee {employee_id} not found")

        self.repo.update(employee_id, data)

    def delete_employee(self, employee_id: int) -> None:
        """
        Delete an employee.

        - Hard refs (active work, payroll, history) BLOCK the delete with a useful message.
        - Soft refs (user link, production-move logs) get auto-NULLed so the delete proceeds.

        Raises:
            ValueError: If the employee doesn't exist or has hard references.
        """
        existing = self.repo.get_by_id(employee_id)
        if not existing:
            raise ValueError(f"Employee {employee_id} not found")

        # HARD refs — refuse to delete; protects financial/historical data.
        hard_checks = [
            ("repair_orders",  "estimator_id = ? OR technician_id = ? OR painter_id = ?", "repair order(s)"),
            ("estimates",      "estimator_id = ?",                                          "estimate(s)"),
            ("ro_lines",       "assigned_tech_id = ?",                                      "RO line assignment(s)"),
            ("ro_assignments", "employee_id = ?",                                           "RO team assignment(s)"),
            ("time_cards",     "employee_id = ?",                                           "time card(s)"),
            ("flag_pay",       "employee_id = ?",                                           "flag pay record(s)"),
        ]

        # SOFT refs — auto-NULL these on delete; they're convenience links not data integrity.
        soft_unlinks = [
            ("users",         "employee_id"),
            ("vehicle_moves", "moved_by"),
        ]

        in_use = []
        with get_db() as db:
            for table, where, label in hard_checks:
                try:
                    n_args = where.count("?")
                    n = db.execute(
                        f"SELECT COUNT(*) AS n FROM {table} WHERE {where}",
                        (employee_id,) * n_args,
                    ).fetchone()["n"]
                except Exception:
                    n = 0
                if n:
                    in_use.append(f"{n} {label}")

        if in_use:
            name = f"{existing.get('first_name','')} {existing.get('last_name','')}".strip() or f"#{employee_id}"
            raise ValueError(
                f"Cannot delete {name} — they're referenced by " + ", ".join(in_use)
                + ". Set their status to Inactive instead, which keeps the historical data intact."
            )

        # Auto-unlink soft refs, then delete.
        with get_db() as db:
            for table, col in soft_unlinks:
                try:
                    db.execute(f"UPDATE {table} SET {col} = NULL WHERE {col} = ?", (employee_id,))
                except Exception:
                    pass  # table may not exist on older installs
            db.commit()

        self.repo.delete(employee_id)
