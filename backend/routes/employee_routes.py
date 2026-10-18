"""
Employee routes: manage employees.
GET / - list (?active_only=true)
GET /{id} - get with history
POST / - create
PUT /{id} - update
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.employee_service import EmployeeService

router = APIRouter(prefix="/api/employees", tags=["employees"])
service = EmployeeService()


class EmployeeIn(BaseModel):
    employee_code: Optional[str] = None
    first_name: str
    last_name: str
    role: str = "technician"
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    hire_date: Optional[str] = None
    hourly_rate: Optional[float] = None
    flag_rate: Optional[float] = None
    is_active: int = 1
    notes: Optional[str] = None


@router.get("")
def list_employees(active_only: bool = Query(True)):
    """List employees with optional active_only filter."""
    try:
        employees = service.list_employees(active_only=active_only)
        return employees
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{employee_id}")
def get_employee(employee_id: int):
    """Get an employee by ID with history (time cards and history)."""
    try:
        employee = service.get_employee(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
        return employee
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_employee(data: EmployeeIn):
    """Create a new employee."""
    try:
        employee_id = service.create_employee(data.dict())
        return {"id": employee_id, "message": "Employee created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{employee_id}")
def update_employee(employee_id: int, data: EmployeeIn):
    """Update an existing employee."""
    try:
        service.update_employee(employee_id, data.dict(exclude_unset=True))
        return {"id": employee_id, "message": "Employee updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{employee_id}")
def delete_employee(employee_id: int):
    """Delete an employee (refuses if referenced by ROs, time cards, etc.)."""
    try:
        service.delete_employee(employee_id)
        return {"message": "Employee deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
