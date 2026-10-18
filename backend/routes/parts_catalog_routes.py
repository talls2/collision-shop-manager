"""
Parts Catalog routes — the price book.
GET    /api/parts-catalog            list (?search=)
GET    /api/parts-catalog/lookup/{n} fetch by part_number (for autocomplete prefill)
POST   /api/parts-catalog            upsert by part_number
PUT    /api/parts-catalog/{id}       edit fields
DELETE /api/parts-catalog/{id}       remove
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.parts_catalog_service import PartsCatalogService

router = APIRouter(prefix="/api/parts-catalog", tags=["parts-catalog"])
service = PartsCatalogService()


class PartIn(BaseModel):
    part_number: str
    description: Optional[str] = None
    standard_price: Optional[float] = 0
    standard_cost: Optional[float] = 0
    part_type: Optional[str] = None
    preferred_vendor_id: Optional[int] = None
    vehicle_compat: Optional[str] = None
    notes: Optional[str] = None


class PartUpdate(BaseModel):
    description: Optional[str] = None
    standard_price: Optional[float] = None
    standard_cost: Optional[float] = None
    part_type: Optional[str] = None
    preferred_vendor_id: Optional[int] = None
    vehicle_compat: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_parts(search: Optional[str] = Query(None)):
    try:
        return service.list_all(search=search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lookup/{part_number}")
def lookup_part(part_number: str):
    """Fetch a catalog entry by part_number — used by add-line autocomplete."""
    row = service.get_by_part_number(part_number)
    if not row:
        raise HTTPException(status_code=404, detail="Not in catalog")
    return row


@router.post("")
def upsert_part(data: PartIn):
    """Create OR update by part_number. Returns the catalog id."""
    try:
        catalog_id = service.upsert(data.dict())
        return {"id": catalog_id, "message": "Part saved to catalog"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{catalog_id}")
def update_part(catalog_id: int, data: PartUpdate):
    try:
        service.update(catalog_id, data.dict(exclude_unset=True))
        return {"id": catalog_id, "message": "Part updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{catalog_id}")
def delete_part(catalog_id: int):
    try:
        service.delete(catalog_id)
        return {"message": "Part removed from catalog"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
