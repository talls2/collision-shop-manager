"""
Services package for shop management application.
Exports all service classes for import by API routes and controllers.
"""
from .customer_service import CustomerService
from .vehicle_service import VehicleService
from .estimate_service import EstimateService
from .repair_order_service import RepairOrderService
from .employee_service import EmployeeService
from .vendor_service import VendorService
from .insurance_service import InsuranceService
from .timecard_service import TimeCardService
from .shop_service import ShopService
from .report_service import ReportService
from .dashboard_service import DashboardService

__all__ = [
    "CustomerService",
    "VehicleService",
    "EstimateService",
    "RepairOrderService",
    "EmployeeService",
    "VendorService",
    "InsuranceService",
    "TimeCardService",
    "ShopService",
    "ReportService",
    "DashboardService",
]
