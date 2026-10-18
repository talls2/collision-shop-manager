"""
ReportService: Business logic for shop reporting and analytics.
Encapsulates report generation and data aggregation.
Delegates data access to ReportRepository.
"""
from repositories.report_repository import ReportRepository


class ReportService:
    """Service for generating shop reports and analytics."""

    def __init__(self):
        self.repo = ReportRepository()

    def production_summary(self, start_date: str | None = None, end_date: str | None = None) -> dict:
        """
        Generate production summary report.

        Returns counts and totals of repair orders and estimates by status,
        with optional date range filtering.

        Args:
            start_date: Start date for report (ISO format: "2026-04-15")
            end_date: End date for report (ISO format: "2026-04-15")

        Returns:
            Dict with:
                - repair_orders: List of RO status summaries
                - estimates: List of estimate status summaries
                - date_range: Dict with start and end dates
        """
        return self.repo.production_summary(start_date=start_date, end_date=end_date)

    def ar_aging(self) -> list[dict]:
        """
        Generate accounts receivable aging report.

        Breaks down outstanding balances by age:
        0-30 days, 31-60 days, 61-90 days, 90+ days.

        Returns:
            List of aging bucket dictionaries with counts and balance amounts
        """
        return self.repo.ar_aging()

    def employee_productivity(self) -> list[dict]:
        """
        Generate employee productivity report.

        Shows hours worked and repair orders completed per active employee.

        Returns:
            List of employee productivity dictionaries sorted by hours worked
        """
        return self.repo.employee_productivity()

    def parts_summary(self) -> list[dict]:
        """
        Generate parts usage and vendor summary.

        Shows parts costs by vendor and line item counts.

        Returns:
            List of vendor parts summary dictionaries sorted by total cost
        """
        return self.repo.parts_summary()

    def cycle_time(self) -> dict:
        """
        Generate cycle time analysis report.

        Calculates average, min, and max time from RO creation to completion
        for completed and closed repair orders.

        Returns:
            Dict with:
                - avg_days_to_complete: Average days to completion
                - min_days: Minimum days
                - max_days: Maximum days
                - total_completed: Count of completed ROs
        """
        return self.repo.cycle_time()
