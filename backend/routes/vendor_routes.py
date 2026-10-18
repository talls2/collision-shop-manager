"""
Vendor routes: manage vendors.
GET / - list (?search=)
POST / - create
PUT /{id} - update
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.vendor_service import VendorService

router = APIRouter(prefix="/api/vendors", tags=["vendors"])
service = VendorService()


class VendorIn(BaseModel):
    vendor_name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    account_number: Optional[str] = None
    vendor_type: str = "parts"
    notes: Optional[str] = None


@router.get("")
def list_vendors(search: Optional[str] = Query(None)):
    """List all vendors with optional search filter."""
    try:
        vendors = service.list_vendors(search=search)
        return vendors
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_vendor(data: VendorIn):
    """Create a new vendor."""
    try:
        vendor_id = service.create_vendor(data.dict())
        return {"id": vendor_id, "message": "Vendor created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{vendor_id}")
def update_vendor(vendor_id: int, data: VendorIn):
    """Update an existing vendor."""
    try:
        service.update_vendor(vendor_id, data.dict(exclude_unset=True))
        return {"id": vendor_id, "message": "Vendor updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{vendor_id}")
def delete_vendor(vendor_id: int):
    """Delete a vendor (refuses if referenced by RO lines or part invoices)."""
    try:
        service.delete_vendor(vendor_id)
        return {"message": "Vendor deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
