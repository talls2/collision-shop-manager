"""
Estimate routes: manage estimates.
GET / - list (?status=, ?search=)
GET /{id} - get full estimate with lines
POST / - create
PUT /{id} - update
POST /{id}/lines - add line item
DELETE /{id}/lines/{line_id} - delete line
POST /{id}/convert-to-ro - convert estimate to repair order
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.estimate_service import EstimateService

router = APIRouter(prefix="/api/estimates", tags=["estimates"])
service = EstimateService()


class EstimateIn(BaseModel):
    customer_id: int
    vehicle_id: Optional[int] = None
    insurance_company_id: Optional[int] = None
    insurance_agent_id: Optional[int] = None
    estimator_id: Optional[int] = None
    claim_number: Optional[str] = None
    policy_number: Optional[str] = None
    deductible: float = 0
    status: str = "pending"
    loss_date: Optional[str] = None
    point_of_impact: Optional[str] = None
    damage_description: Optional[str] = None
    tax_exempt: Optional[int] = None
    closed_date: Optional[str] = None
    notes: Optional[str] = None


class EstimateLineIn(BaseModel):
    line_type: str = "labor"
    operation: Optional[str] = None
    description: str = ""
    part_number: Optional[str] = None
    part_type: Optional[str] = None
    quantity: float = 1
    labor_hours: float = 0
    labor_rate: float = 0
    paint_hours: float = 0
    paint_rate: float = 0
    part_price: float = 0
    part_cost: float = 0
    is_supplement: int = 0
    supplement_number: int = 0
    taxable: Optional[int] = None
    notes: Optional[str] = None


@router.get("")
def list_estimates(status: Optional[str] = Query(None), search: Optional[str] = Query(None)):
    """List estimates with optional status and search filtering."""
    try:
        estimates = service.list_estimates(status=status, search=search)
        return estimates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/follow-up")
def list_follow_up(min_days: int = Query(7, ge=1, le=365), limit: int = Query(200, ge=1, le=1000)):
    """
    List estimates that need follow-up: no status change in at least min_days days,
    excluding terminal statuses (converted, rejected).
    Ordered oldest-first (most stale at the top).
    """
    try:
        from config.database import get_db, rows_to_list
        with get_db() as db:
            rows = db.execute(
                """
                SELECT e.id, e.estimate_number, e.status, e.estimate_date,
                       e.updated_at, e.total_amount, e.closed_date,
                       c.first_name, c.last_name, c.company_name,
                       c.phone_home, c.phone_cell, c.email,
                       v.year, v.make, v.model, v.vin,
                       CAST((julianday('now') - julianday(e.updated_at)) AS INTEGER) AS days_stale
                FROM estimates e
                LEFT JOIN customers c ON e.customer_id = c.id
                LEFT JOIN vehicles  v ON e.vehicle_id  = v.id
                WHERE e.status NOT IN ('converted', 'rejected')
                  AND julianday('now') - julianday(e.updated_at) >= ?
                ORDER BY e.updated_at ASC
                LIMIT ?
                """,
                (min_days, limit),
            ).fetchall()
            return rows_to_list(rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{estimate_id}")
def get_estimate(estimate_id: int):
    """Get a complete estimate with all details and line items."""
    try:
        estimate = service.get_estimate(estimate_id)
        if not estimate:
            raise HTTPException(status_code=404, detail=f"Estimate {estimate_id} not found")
        return estimate
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_estimate(data: EstimateIn):
    """Create a new estimate."""
    try:
        estimate_id = service.create_estimate(data.dict())
        return {"id": estimate_id, "message": "Estimate created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{estimate_id}")
def update_estimate(estimate_id: int, data: EstimateIn):
    """Update an existing estimate."""
    try:
        service.update_estimate(estimate_id, data.dict(exclude_unset=True))
        return {"id": estimate_id, "message": "Estimate updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{estimate_id}/lines")
def add_estimate_line(estimate_id: int, data: EstimateLineIn):
    """Add a line item to an estimate."""
    try:
        line_id = service.add_line(estimate_id, data.dict())
        return {"id": line_id, "message": "Line item added successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{estimate_id}/lines/{line_id}")
def delete_estimate_line(estimate_id: int, line_id: int):
    """Delete a line item from an estimate."""
    try:
        service.delete_line(estimate_id, line_id)
        return {"message": "Line item deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EstLineUpdate(BaseModel):
    taxable: Optional[int] = None
    operation: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    labor_hours: Optional[float] = None
    labor_rate: Optional[float] = None
    paint_hours: Optional[float] = None
    paint_rate: Optional[float] = None
    part_price: Optional[float] = None
    part_cost: Optional[float] = None
    notes: Optional[str] = None


@router.patch("/{estimate_id}/lines/{line_id}")
def update_estimate_line(estimate_id: int, line_id: int, data: EstLineUpdate):
    """Update fields on an estimate line (e.g. flip taxable) and recompute totals."""
    try:
        service.update_line(estimate_id, line_id, data.dict(exclude_unset=True))
        return {"id": line_id, "message": "Line updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{estimate_id}/lines/{line_id}/move")
def move_estimate_line(estimate_id: int, line_id: int, direction: str = Query(..., pattern="^(up|down)$")):
    """Reorder a line — swap line_number with the neighbor up or down."""
    try:
        service.move_line(estimate_id, line_id, direction)
        return {"id": line_id, "message": f"Line moved {direction}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{estimate_id}")
def delete_estimate(estimate_id: int):
    """Delete an estimate. Refuses if it's been converted to an RO."""
    try:
        service.delete_estimate(estimate_id)
        return {"message": "Estimate deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TeamMember(BaseModel):
    employee_id: int
    role: str


class ConvertToRoIn(BaseModel):
    team: Optional[list[TeamMember]] = None


@router.post("/{estimate_id}/convert-to-ro")
def convert_estimate_to_ro(estimate_id: int, data: Optional[ConvertToRoIn] = None):
    """Convert an estimate to a repair order. Requires at least one worker assigned."""
    try:
        team_list = [m.dict() for m in data.team] if (data and data.team) else None
        result = service.convert_to_ro(estimate_id, team=team_list)
        if isinstance(result, dict):
            return result
        return {"id": result, "message": "Estimate converted to repair order successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
