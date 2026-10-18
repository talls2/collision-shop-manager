"""
TimeCardService: Business logic for time card management.
Encapsulates validation and automatic hour calculation.
Delegates data access to TimeCardRepository.
"""
from repositories.timecard_repository import TimeCardRepository


class TimeCardService:
    """Service for managing employee time cards."""

    def __init__(self):
        self.repo = TimeCardRepository()

    def list_timecards(self, employee_id: int | None = None, ro_id: int | None = None) -> list[dict]:
        """
        List time cards with optional filtering by employee or repair order.

        Args:
            employee_id: Filter by employee ID
            ro_id: Filter by repair order ID

        Returns:
            List of time card dictionaries with employee and RO info
        """
        return self.repo.list_with_details(employee_id=employee_id, ro_id=ro_id)

    def get_timecard(self, timecard_id: int) -> dict | None:
        """
        Get a time card by ID.

        Args:
            timecard_id: Time card ID

        Returns:
            Time card dictionary or None if not found
        """
        return self.repo.get_by_id(timecard_id)

    def create_timecard(self, data: dict) -> int:
        """
        Create a new time card with optional automatic hour calculation.

        Args:
            data: Time card data dict. Should include:
                - employee_id: Employee ID
                - clock_in: Clock-in datetime (ISO format)
                - clock_out (optional): Clock-out datetime (ISO format)
                  If provided, hours will be auto-calculated
                - ro_id (optional): Repair order ID
                - notes (optional): Notes

        Returns:
            New time card ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not data.get("employee_id"):
            raise ValueError("Time card must have an employee_id")
        if not data.get("clock_in"):
            raise ValueError("Time card must have a clock_in time")

        # Block double clock-in: refuse if the employee already has an open
        # session (no clock_out). Names the active job so the worker knows where
        # to clock out from. Only applies when starting a NEW open session.
        if not data.get("clock_out"):
            from config.database import get_db
            with get_db() as db:
                existing = db.execute(
                    """SELECT tc.id, tc.ro_id, tc.activity_type, ro.ro_number
                       FROM time_cards tc
                       LEFT JOIN repair_orders ro ON tc.ro_id = ro.id
                       WHERE tc.employee_id = ? AND tc.clock_out IS NULL
                       ORDER BY tc.clock_in DESC LIMIT 1""",
                    (data["employee_id"],),
                ).fetchone()
            if existing:
                ro_label = existing["ro_number"] if existing["ro_number"] else (existing["activity_type"] or "general")
                raise ValueError(
                    f"You're already clocked in to {ro_label}. Clock out from there first before starting a new session."
                )

        # Auto-calculate hours if clock_out is provided
        if data.get("clock_out"):
            hours = self.repo.calc_hours(data["clock_in"], data["clock_out"])
            data["hours_worked"] = hours

        return self.repo.insert(data)

    def update_timecard(self, timecard_id: int, data: dict) -> None:
        """
        Update a time card (e.g., set clock_out, hours_worked).

        Args:
            timecard_id: Time card ID
            data: Fields to update

        Raises:
            ValueError: If time card not found
        """
        existing = self.repo.get_by_id(timecard_id)
        if not existing:
            raise ValueError(f"Time card {timecard_id} not found")

        # Auto-calculate hours if clock_out provided but hours_worked not
        if data.get("clock_out") and not data.get("hours_worked"):
            data["hours_worked"] = self.repo.calc_hours(existing["clock_in"], data["clock_out"])

        self.repo.update(timecard_id, data)

    def clock_out(self, timecard_id: int, clock_out_time: str) -> None:
        """
        Clock out an employee and auto-calculate hours worked.

        Args:
            timecard_id: Time card ID
            clock_out_time: Clock-out datetime (ISO format)

        Raises:
            ValueError: If time card not found
        """
        # Get existing time card
        existing = self.repo.get_by_id(timecard_id)
        if not existing:
            raise ValueError(f"Time card {timecard_id} not found")

        # Calculate hours
        hours = self.repo.calc_hours(existing["clock_in"], clock_out_time)

        # Update time card with clock_out and hours_worked
        self.repo.update(timecard_id, {
            "clock_out": clock_out_time,
            "hours_worked": hours
        })
