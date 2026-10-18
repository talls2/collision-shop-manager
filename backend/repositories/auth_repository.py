"""
AuthRepository: User and session management.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class AuthRepository(BaseRepository):
    table_name = "users"
    order_by = "display_name ASC"

    def get_by_username(self, username: str) -> dict | None:
        """Get a user by username."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            ).fetchone()
        return row_to_dict(row) if row else None

    def get_by_token(self, token: str) -> dict | None:
        """Get user by session token (if not expired)."""
        with get_db() as db:
            row = db.execute(
                """
                SELECT u.* FROM users u
                JOIN user_sessions s ON u.id = s.user_id
                WHERE s.token = ? AND s.expires_at > datetime('now')
                AND u.is_active = 1
                """,
                (token,)
            ).fetchone()
        return row_to_dict(row) if row else None

    def create_session(self, user_id: int, token: str, hours: int = 12) -> None:
        """Create a new session token."""
        with get_db() as db:
            db.execute(
                """INSERT INTO user_sessions (user_id, token, expires_at)
                VALUES (?, ?, datetime('now', '+' || ? || ' hours'))""",
                (user_id, token, hours)
            )
            db.commit()

    def delete_session(self, token: str) -> None:
        """Delete a session (logout)."""
        with get_db() as db:
            db.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
            db.commit()

    def update_last_login(self, user_id: int) -> None:
        """Update last login timestamp."""
        with get_db() as db:
            db.execute(
                "UPDATE users SET last_login = datetime('now') WHERE id = ?",
                (user_id,)
            )
            db.commit()

    def cleanup_expired(self) -> None:
        """Remove expired sessions."""
        with get_db() as db:
            db.execute("DELETE FROM user_sessions WHERE expires_at < datetime('now')")
            db.commit()

    def list_users(self) -> list[dict]:
        """List all users (without pin hashes)."""
        with get_db() as db:
            rows = db.execute(
                """SELECT id, username, display_name, role, employee_id,
                   is_active, last_login, created_at
                FROM users ORDER BY display_name"""
            ).fetchall()
        return rows_to_list(rows)
