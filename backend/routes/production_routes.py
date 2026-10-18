"""
Production routes: manage production schedule.
GET / - list (?status=, ?department=)
GET /ro/{ro_id} - get schedule for a specific RO
POST / - create entry
PUT /{id} - update entry
PUT /{id}/status - update status only
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.production_service import ProductionService

router = APIRouter(prefix="/api/production", tags=["production"])
service = ProductionService()


class ProductionIn(BaseModel):
    ro_id: int
    department: Optional[str] = None
    scheduled_date: Optional[str] = None
    estimated_hours: float = 0
    assigned_tech_id: Optional[int] = None
    status: str = "scheduled"
    notes: Optional[str] = None


class StatusIn(BaseModel):
    status: str


@router.get("")
def list_production(status: Optional[str] = Query(None),
                    department: Optional[str] = Query(None)):
    """List production schedule with optional status and department filters."""
    try:
        entries = service.list_schedule(status=status, department=department)
        return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ro/{ro_id}")
def get_production_by_ro(ro_id: int):
    """Get production schedule entries for a specific repair order."""
    try:
        entries = service.get_by_ro(ro_id)
        return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_production_entry(data: ProductionIn):
    """Create a new production schedule entry."""
    try:
        entry_id = service.create_entry(data.dict())
        return {"id": entry_id, "message": "Production entry created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{entry_id}")
def update_production_entry(entry_id: int, data: ProductionIn):
    """Update a production schedule entry."""
    try:
        service.update_entry(entry_id, data.dict(exclude_unset=True))
        return {"id": entry_id, "message": "Production entry updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{entry_id}/status")
def update_production_status(entry_id: int, data: StatusIn):
    """Update just the status of a production entry."""
    try:
        service.update_status(entry_id, data.status)
        return {"id": entry_id, "message": "Status updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
