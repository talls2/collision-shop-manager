"""
Dashboard routes: provides shop overview and statistics.
GET / - dashboard statistics
"""
from fastapi import APIRouter, HTTPException
from services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
service = DashboardService()


@router.get("")
def get_dashboard_stats():
    """Get comprehensive dashboard statistics."""
    try:
        stats = service.get_dashboard_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
