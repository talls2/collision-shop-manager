"""
Vehicle routes: manage vehicles.
GET / - list (optional ?search=)
GET /{id} - get with owner
POST / - create
PUT /{id} - update
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.vehicle_service import VehicleService

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])
service = VehicleService()


class VehicleIn(BaseModel):
    customer_id: int
    vehicle_type: Optional[str] = None
    vin: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    submodel: Optional[str] = None
    color: Optional[str] = None
    license_plate: Optional[str] = None
    license_state: Optional[str] = None
    mileage: Optional[int] = None
    engine_hours: Optional[int] = None
    length_feet: Optional[int] = None
    axle_count: Optional[int] = None
    production_date: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_vehicles(search: Optional[str] = Query(None), customer_id: Optional[int] = Query(None)):
    """List all vehicles with optional search or customer filter."""
    try:
        vehicles = service.list_vehicles(search=search, customer_id=customer_id)
        return vehicles
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{vehicle_id}")
def get_vehicle(vehicle_id: int):
    """Get a vehicle by ID with owner information."""
    try:
        vehicle = service.get_vehicle(vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")
        return vehicle
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_vehicle(data: VehicleIn):
    """Create a new vehicle."""
    try:
        vehicle_id = service.create_vehicle(data.dict())
        return {"id": vehicle_id, "message": "Vehicle created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{vehicle_id}")
def update_vehicle(vehicle_id: int, data: VehicleIn):
    """Update an existing vehicle."""
    try:
        service.update_vehicle(vehicle_id, data.dict(exclude_unset=True))
        return {"id": vehicle_id, "message": "Vehicle updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
