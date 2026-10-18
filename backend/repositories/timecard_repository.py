"""
TimeCardRepository: Time card CRUD and calculations.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository
from datetime import datetime


class TimeCardRepository(BaseRepository):
    table_name = "time_cards"
    order_by = "clock_in DESC"

    def list_with_details(self, employee_id: int | None = None,
                         ro_id: int | None = None,
                         limit: int = 500) -> list[dict]:
        """
        List time cards with employee and repair order info joined.
        Optionally filter by employee_id and/or ro_id.
        """
        query = """
            SELECT tc.*, e.first_name, e.last_name,
                   ro.ro_number
            FROM time_cards tc
            LEFT JOIN employees e ON tc.employee_id = e.id
            LEFT JOIN repair_orders ro ON tc.ro_id = ro.id
            WHERE 1=1
        """
        params = []

        if employee_id:
            query += " AND tc.employee_id = ?"
            params.append(employee_id)

        if ro_id:
            query += " AND tc.ro_id = ?"
            params.append(ro_id)

        query += f" ORDER BY {self.order_by} LIMIT ?"
        params.append(limit)

        with get_db() as db:
            rows = db.execute(query, params).fetchall()
        return rows_to_list(rows)

    def calc_hours(self, clock_in: str, clock_out: str) -> float:
        """
        Calculate hours worked between two datetime strings.
        Tolerates several formats stored over the project's history:
          - "2026-04-15T13:00:00.000Z"  (current — proper ISO UTC)
          - "2026-04-15T13:00:00+00:00" (proper ISO with explicit offset)
          - "2026-04-15 13:00:00"       (legacy — UTC time written without TZ marker)
        Both inputs are treated on the same UTC scale; the result is never negative.
        """
        def parse(s):
            if not s:
                return None
            s = s.replace(' ', 'T').rstrip('Zz')
            # Strip trailing +HH:MM / -HH:MM offset (Python<3.11 fromisoformat is picky)
            if len(s) >= 6 and s[-3] == ':' and s[-6] in '+-':
                s = s[:-6]
            # Drop microseconds tail
            if '.' in s:
                s = s.split('.', 1)[0]
            try:
                return datetime.fromisoformat(s)
            except (ValueError, AttributeError):
                return None

        in_time = parse(clock_in)
        out_time = parse(clock_out)
        if not in_time or not out_time:
            return 0.0

        delta = out_time - in_time
        hours = delta.total_seconds() / 3600.0
        return max(0.0, round(hours, 2))
