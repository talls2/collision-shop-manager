"""
AuthService: Authentication and session management.
PIN-based login for shop environments — techs tap a PIN, admins get full access.
"""
import hashlib
import secrets
from repositories.auth_repository import AuthRepository


class AuthService:
    """Service for PIN-based authentication."""

    def __init__(self):
        self.repo = AuthRepository()

    @staticmethod
    def _hash_pin(pin: str) -> str:
        """Hash a PIN. Simple SHA256 for now."""
        return hashlib.sha256(pin.encode()).hexdigest()

    def login(self, username: str, pin: str) -> dict:
        """
        Authenticate a user by username + PIN.

        Returns:
            Dict with token, user info, and role

        Raises:
            ValueError: If credentials are invalid
        """
        user = self.repo.get_by_username(username)
        if not user:
            raise ValueError("Invalid username or PIN")

        if user["pin_hash"] != self._hash_pin(pin):
            raise ValueError("Invalid username or PIN")

        # Create session
        token = secrets.token_hex(32)
        self.repo.create_session(user["id"], token, hours=12)
        self.repo.update_last_login(user["id"])

        return {
            "token": token,
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "employee_id": user["employee_id"],
        }

    def validate_token(self, token: str) -> dict | None:
        """Validate a session token and return user info."""
        if not token:
            return None
        return self.repo.get_by_token(token)

    def logout(self, token: str) -> None:
        """Invalidate a session token."""
        self.repo.delete_session(token)

    def list_users(self) -> list[dict]:
        """List all users (admin only)."""
        return self.repo.list_users()

    def create_user(self, data: dict) -> int:
        """Create a new user account."""
        if not data.get("username"):
            raise ValueError("Username is required")
        if not data.get("pin"):
            raise ValueError("PIN is required")
        if len(data["pin"]) < 4:
            raise ValueError("PIN must be at least 4 digits")

        # Check username uniqueness
        existing = self.repo.get_by_username(data["username"])
        if existing:
            raise ValueError(f"Username '{data['username']}' already taken")

        user_data = {
            "username": data["username"],
            "pin_hash": self._hash_pin(data["pin"]),
            "display_name": data.get("display_name", data["username"]),
            "role": data.get("role", "worker"),
            "employee_id": data.get("employee_id"),
            "is_active": 1,
        }
        return self.repo.insert(user_data)

    def change_pin(self, user_id: int, old_pin: str, new_pin: str) -> None:
        """Change a user's PIN."""
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if user["pin_hash"] != self._hash_pin(old_pin):
            raise ValueError("Current PIN is incorrect")

        if len(new_pin) < 4:
            raise ValueError("New PIN must be at least 4 digits")

        self.repo.update(user_id, {"pin_hash": self._hash_pin(new_pin)})

    def admin_reset_pin(self, user_id: int, new_pin: str) -> None:
        """Admin-only: reset a user's PIN without knowing the old one."""
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if not new_pin or len(new_pin) < 4:
            raise ValueError("New PIN must be at least 4 digits")
        self.repo.update(user_id, {"pin_hash": self._hash_pin(new_pin)})

    def update_user(self, user_id: int, data: dict) -> None:
        """
        Update a user's profile fields (display_name, role, employee_id, is_active).
        Username and PIN are NOT updated through this method.
        """
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        allowed = {"display_name", "role", "employee_id", "is_active"}
        clean = {k: v for k, v in data.items() if k in allowed and v is not None}
        if "is_active" in clean:
            clean["is_active"] = 1 if clean["is_active"] else 0
        if not clean:
            return
        self.repo.update(user_id, clean)

    def delete_user(self, user_id: int, requester_id: int) -> None:
        """
        Delete a user account. Cleans up sessions automatically.

        Refuses to:
          - delete yourself (so you can't lock yourself out by accident)
          - delete the last remaining admin

        Raises:
            ValueError: on any of the above checks.
        """
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if user_id == requester_id:
            raise ValueError("You can't delete the account you're signed in with. Sign in as a different admin first.")

        if user.get("role") == "admin":
            from config.database import get_db
            with get_db() as db:
                admin_count = db.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1"
                ).fetchone()["n"]
            if admin_count <= 1:
                raise ValueError("Can't delete the last admin account. Promote another user to admin first.")

        # Drop sessions, then the user.
        from config.database import get_db
        with get_db() as db:
            db.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            db.commit()
        self.repo.delete(user_id)
