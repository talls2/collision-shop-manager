"""
Customer routes: manage customers.
GET / - list (optional ?search=)
GET /{id} - get with relations
POST / - create
PUT /{id} - update
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.customer_service import CustomerService

router = APIRouter(prefix="/api/customers", tags=["customers"])
service = CustomerService()


class CustomerIn(BaseModel):
    customer_type: str = "individual"
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone_home: Optional[str] = None
    phone_work: Optional[str] = None
    phone_cell: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_zip: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_customers(search: Optional[str] = Query(None)):
    """List all customers with optional search filter."""
    try:
        customers = service.list_customers(search=search)
        return customers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}")
def get_customer(customer_id: int):
    """Get a customer by ID with all related data."""
    try:
        customer = service.get_customer(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
        return customer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_customer(data: CustomerIn):
    """Create a new customer."""
    try:
        customer_id = service.create_customer(data.dict())
        return {"id": customer_id, "message": "Customer created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{customer_id}")
def update_customer(customer_id: int, data: CustomerIn):
    """Update an existing customer."""
    try:
        service.update_customer(customer_id, data.dict(exclude_unset=True))
        return {"id": customer_id, "message": "Customer updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
