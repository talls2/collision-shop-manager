"""
DashboardService: Business logic for dashboard statistics and summaries.
Aggregates data from multiple repositories to provide dashboard insights.
"""
from repositories.repair_order_repository import RepairOrderRepository
from repositories.estimate_repository import EstimateRepository
from repositories.customer_repository import CustomerRepository
from repositories.vehicle_repository import VehicleRepository


class DashboardService:
    """Service for aggregating dashboard statistics."""

    def __init__(self):
        self.ro_repo = RepairOrderRepository()
        self.estimate_repo = EstimateRepository()
        self.customer_repo = CustomerRepository()
        self.vehicle_repo = VehicleRepository()

    def get_dashboard_stats(self) -> dict:
        """
        Get comprehensive dashboard statistics.

        Returns a dict with:
            - open_ros: Count of open repair orders
            - completed_ros: Count of completed repair orders
            - pending_estimates: Count of pending estimates
            - total_customers: Total customer count
            - total_vehicles: Total vehicle count
            - total_revenue: Sum of total_amount from all repair orders
            - outstanding_balance: Sum of balance_due from all repair orders
            - recent_ros: List of 10 most recent ROs with customer/vehicle info
            - recent_estimates: List of 10 most recent estimates with customer/vehicle info

        Returns:
            Dashboard statistics dictionary
        """
        stats = {}

        # Count open and completed ROs
        open_count = self.ro_repo.count(where="status = ?", params=("open",))
        completed_count = self.ro_repo.count(where="status IN ('completed', 'closed')", params=())
        stats["open_ros"] = open_count
        stats["completed_ros"] = completed_count

        # Count pending estimates
        pending_estimates = self.estimate_repo.count(where="status = ?", params=("pending",))
        stats["pending_estimates"] = pending_estimates

        # Count customers and vehicles
        stats["total_customers"] = self.customer_repo.count()
        stats["total_vehicles"] = self.vehicle_repo.count()

        # Calculate total revenue and outstanding balance from repair orders
        from config.database import get_db, rows_to_list
        with get_db() as db:
            # Get revenue and balance info
            row = db.execute(
                """
                SELECT
                    COALESCE(SUM(total_amount), 0) as total_revenue,
                    COALESCE(SUM(balance_due), 0) as outstanding_balance
                FROM repair_orders
                """
            ).fetchone()

            stats["total_revenue"] = float(row["total_revenue"] or 0)
            stats["outstanding_balance"] = float(row["outstanding_balance"] or 0)

        # Get recent ROs (last 10) with customer/vehicle info
        recent_ros = self.ro_repo.list_with_details(limit=10)
        stats["recent_ros"] = recent_ros

        # Get recent estimates (last 10) with customer/vehicle info
        recent_estimates = self.estimate_repo.list_with_details(limit=10)
        stats["recent_estimates"] = recent_estimates

        # Follow-Up Needed: active estimates with no status change in >7 days.
        # Terminal statuses (converted/rejected) are excluded — those are done.
        with get_db() as db:
            rows = db.execute(
                """
                SELECT e.id, e.estimate_number, e.status, e.estimate_date,
                       e.updated_at, e.total_amount,
                       c.first_name, c.last_name, c.company_name, c.phone_home,
                       v.year, v.make, v.model, v.vin,
                       CAST((julianday('now') - julianday(e.updated_at)) AS INTEGER) AS days_stale
                FROM estimates e
                LEFT JOIN customers c ON e.customer_id = c.id
                LEFT JOIN vehicles v  ON e.vehicle_id  = v.id
                WHERE e.status NOT IN ('converted', 'rejected')
                  AND julianday('now') - julianday(e.updated_at) >= 7
                ORDER BY e.updated_at ASC
                LIMIT 25
                """
            ).fetchall()
            stats["follow_up_needed"] = rows_to_list(rows)

        return stats
