"""
Insurance routes: manage insurance companies and agents.
GET / - list (?search=)
GET /{id} - get with agents
POST / - create
PUT /{id} - update
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.insurance_service import InsuranceService

router = APIRouter(prefix="/api/insurance", tags=["insurance"])
service = InsuranceService()


class InsuranceIn(BaseModel):
    company_name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    policy_prefix: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_insurance(search: Optional[str] = Query(None)):
    """List all insurance companies with optional search filter."""
    try:
        insurance_companies = service.list_insurance(search=search)
        return insurance_companies
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{insurance_id}")
def get_insurance(insurance_id: int):
    """Get an insurance company by ID with all its agents."""
    try:
        insurance = service.get_insurance(insurance_id)
        if not insurance:
            raise HTTPException(status_code=404, detail=f"Insurance company {insurance_id} not found")
        return insurance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_insurance(data: InsuranceIn):
    """Create a new insurance company."""
    try:
        insurance_id = service.create_insurance(data.dict())
        return {"id": insurance_id, "message": "Insurance company created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{insurance_id}")
def update_insurance(insurance_id: int, data: InsuranceIn):
    """Update an existing insurance company."""
    try:
        service.update_insurance(insurance_id, data.dict(exclude_unset=True))
        return {"id": insurance_id, "message": "Insurance company updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
