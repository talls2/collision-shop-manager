"""
Auth routes: login, logout, session management.
POST /login - authenticate with username + PIN
POST /logout - invalidate session
GET /me - get current user info
GET /users - list users (admin only)
POST /users - create user (admin only)
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
service = AuthService()


class LoginIn(BaseModel):
    username: str
    pin: str


class UserCreateIn(BaseModel):
    username: str
    pin: str
    display_name: Optional[str] = None
    role: str = "worker"
    employee_id: Optional[int] = None


class UserUpdateIn(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[int] = None
    is_active: Optional[int] = None


class PinResetIn(BaseModel):
    pin: str


class PinChangeIn(BaseModel):
    old_pin: str
    new_pin: str


def get_current_user(request: Request) -> dict | None:
    """Extract and validate the session token from request headers."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    return service.validate_token(token)


def require_auth(request: Request) -> dict:
    """Require authentication. Returns user or raises 401."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> dict:
    """Require admin role. Returns user or raises 403."""
    user = require_auth(request)
    if user["role"] not in ("admin", "office"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/workers")
def list_workers():
    """List active worker accounts (for touch-screen login grid). No auth required."""
    try:
        users = service.list_users()
        # Only return workers with minimal info for the login grid
        workers = [
            {"id": u["id"], "username": u["username"], "display_name": u["display_name"],
             "role": u["role"], "employee_id": u.get("employee_id")}
            for u in users if u.get("is_active", 1) and u.get("role") == "worker"
        ]
        return workers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(data: LoginIn):
    """Login with username and PIN."""
    try:
        result = service.login(data.username, data.pin)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
def logout(request: Request):
    """Logout and invalidate session."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        service.logout(token)
    return {"message": "Logged out"}


@router.get("/me")
def get_me(request: Request):
    """Get current authenticated user info."""
    user = require_auth(request)
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "employee_id": user["employee_id"],
    }


@router.get("/users")
def list_users(request: Request):
    """List all users (admin/office only)."""
    require_admin(request)
    return service.list_users()


@router.post("/users")
def create_user(data: UserCreateIn, request: Request):
    """Create a new user (admin only)."""
    user = require_auth(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create users")
    try:
        user_id = service.create_user(data.dict())
        return {"id": user_id, "message": "User created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdateIn, request: Request):
    """Update a user's profile (admin only). Cannot change username or PIN through this endpoint."""
    user = require_auth(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update users")
    try:
        service.update_user(user_id, data.dict(exclude_unset=True))
        return {"id": user_id, "message": "User updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/reset-pin")
def reset_user_pin(user_id: int, data: PinResetIn, request: Request):
    """Admin-only: reset a user's PIN without knowing the old one."""
    user = require_auth(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can reset PINs")
    try:
        service.admin_reset_pin(user_id, data.pin)
        return {"id": user_id, "message": "PIN reset successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request):
    """Admin-only: delete a user (refuses self-delete and last-admin delete)."""
    user = require_auth(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete users")
    try:
        service.delete_user(user_id, requester_id=user["id"])
        return {"message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-pin")
def change_my_pin(data: PinChangeIn, request: Request):
    """Self-service: any logged-in user can change their own PIN if they know the current one."""
    user = require_auth(request)
    try:
        service.change_pin(user["id"], data.old_pin, data.new_pin)
        return {"message": "PIN changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
