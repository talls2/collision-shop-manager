"""
Routes package for shop management application.
Exports all route routers for integration into FastAPI app.
"""
from .dashboard_routes import router as dashboard_router
from .customer_routes import router as customer_router
from .vehicle_routes import router as vehicle_router
from .estimate_routes import router as estimate_router
from .repair_order_routes import router as repair_order_router
from .employee_routes import router as employee_router
from .vendor_routes import router as vendor_router
from .insurance_routes import router as insurance_router
from .timecard_routes import router as timecard_router
from .shop_routes import router as shop_router
from .report_routes import router as report_router
from .production_routes import router as production_router
from .auth_routes import router as auth_router
from .export_routes import router as export_router
from .tecstation_routes import router as tecstation_router
from .parts_catalog_routes import router as parts_catalog_router

__all__ = [
    "dashboard_router",
    "customer_router",
    "vehicle_router",
    "estimate_router",
    "repair_order_router",
    "employee_router",
    "vendor_router",
    "insurance_router",
    "timecard_router",
    "shop_router",
    "report_router",
    "production_router",
    "auth_router",
    "export_router",
    "tecstation_router",
    "parts_catalog_router",
]
