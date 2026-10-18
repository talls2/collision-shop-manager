"""
TecStation routes: technician station operations.
GET /board - full shop board (vehicles by department)
GET /my-jobs/{employee_id} - jobs assigned to a tech
GET /history/{ro_id} - vehicle movement history
POST /move - move a vehicle between departments
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.tecstation_service import TecStationService

router = APIRouter(prefix="/api/tecstation", tags=["tecstation"])
service = TecStationService()


class MoveVehicleIn(BaseModel):
    ro_id: int
    to_department: str
    moved_by: Optional[int] = None
    notes: Optional[str] = None


@router.get("/board")
def get_shop_board():
    """Get full shop board showing all vehicles by department."""
    try:
        return service.get_shop_board()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-jobs/{employee_id}")
def get_my_jobs(employee_id: int):
    """Get all jobs assigned to a specific technician."""
    try:
        return service.get_my_jobs(employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{ro_id}")
def get_vehicle_history(ro_id: int):
    """Get movement history for a vehicle/RO."""
    try:
        return service.get_vehicle_history(ro_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/move")
def move_vehicle(data: MoveVehicleIn):
    """Move a vehicle to a new department."""
    try:
        move_id = service.move_vehicle(
            ro_id=data.ro_id,
            to_department=data.to_department,
            moved_by=data.moved_by,
            notes=data.notes,
        )
        return {"id": move_id, "message": f"Vehicle moved to {data.to_department}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
