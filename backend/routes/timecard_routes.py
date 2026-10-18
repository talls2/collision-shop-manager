"""
Timecard routes: manage employee time cards.
GET / - list (?employee_id=, ?ro_id=)
POST / - create
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.timecard_service import TimeCardService

router = APIRouter(prefix="/api/time-cards", tags=["time-cards"])
service = TimeCardService()


class TimeCardIn(BaseModel):
    employee_id: int
    clock_in: str
    clock_out: Optional[str] = None
    ro_id: Optional[int] = None
    activity_type: str = "production"
    hours_worked: float = 0
    notes: Optional[str] = None


class TimeCardUpdate(BaseModel):
    clock_out: Optional[str] = None
    hours_worked: Optional[float] = None
    notes: Optional[str] = None


@router.get("")
def list_timecards(employee_id: Optional[int] = Query(None), ro_id: Optional[int] = Query(None)):
    """List time cards with optional filtering by employee or repair order."""
    try:
        timecards = service.list_timecards(employee_id=employee_id, ro_id=ro_id)
        return timecards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_timecard(data: TimeCardIn):
    """Create a new time card."""
    try:
        timecard_id = service.create_timecard(data.dict())
        return {"id": timecard_id, "message": "Time card created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{timecard_id}")
def update_timecard(timecard_id: int, data: TimeCardUpdate):
    """Update a time card (e.g., clock out)."""
    try:
        service.update_timecard(timecard_id, data.dict(exclude_unset=True))
        return {"id": timecard_id, "message": "Time card updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
