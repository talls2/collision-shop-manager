"""
Shop routes: manage shop configuration and reference data.
GET /info - shop info
PUT /info - update shop info
GET /rates - shop rates
GET /templates - letter templates
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.shop_service import ShopService

router = APIRouter(prefix="/api/shop", tags=["shop"])
service = ShopService()


class ShopInfoIn(BaseModel):
    shop_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    license_number: Optional[str] = None
    notes: Optional[str] = None


@router.get("/info")
def get_shop_info():
    """Get shop information."""
    try:
        info = service.get_info()
        if not info:
            raise HTTPException(status_code=404, detail="Shop information not configured")
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/info")
def update_shop_info(data: ShopInfoIn):
    """Update shop information."""
    try:
        service.update_info(data.dict(exclude_unset=True))
        return {"message": "Shop information updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RateIn(BaseModel):
    rate_name: str
    rate_type: Optional[str] = None
    rate_amount: float


class RateUpdate(BaseModel):
    rate_name: Optional[str] = None
    rate_type: Optional[str] = None
    rate_amount: Optional[float] = None


@router.get("/rates")
def get_shop_rates():
    """Get shop rates (labor rates, etc.)."""
    try:
        rates = service.get_rates()
        return rates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rates")
def create_shop_rate(data: RateIn):
    """Add a new shop rate."""
    try:
        rate_id = service.create_rate(data.dict())
        return {"id": rate_id, "message": "Rate added"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rates/{rate_id}")
def update_shop_rate(rate_id: int, data: RateUpdate):
    """Update an existing shop rate."""
    try:
        service.update_rate(rate_id, data.dict(exclude_unset=True))
        return {"id": rate_id, "message": "Rate updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rates/{rate_id}")
def delete_shop_rate(rate_id: int):
    """Delete a shop rate."""
    try:
        service.delete_rate(rate_id)
        return {"message": "Rate deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
def get_letter_templates():
    """Get letter templates for correspondence."""
    try:
        templates = service.get_templates()
        return templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
