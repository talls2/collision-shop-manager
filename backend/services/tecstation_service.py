"""
TecStationService: Technician station operations.
Handles vehicle movement tracking, department-based job views,
and technician-specific work management.
"""
from config.database import get_db, row_to_dict, rows_to_list


class TecStationService:
    """Service for technician station operations."""

    DEPARTMENTS = [
        "lot", "body", "frame", "mechanical", "paint",
        "detail", "assembly", "glass", "qa", "ready", "delivered"
    ]

    def get_shop_board(self) -> dict:
        """
        Get the full shop board showing where every vehicle is.
        Returns a dict of department -> list of vehicles/ROs.
        """
        with get_db() as db:
            # Get all open ROs with their current department
            ros = rows_to_list(db.execute("""
                SELECT ro.id, ro.ro_number, ro.status, ro.priority,
                       ro.target_delivery_date,
                       c.first_name, c.last_name, c.company_name,
                       v.year, v.make, v.model, v.color, v.license_plate,
                       t.first_name AS tech_first, t.last_name AS tech_last,
                       p.first_name AS painter_first, p.last_name AS painter_last
                FROM repair_orders ro
                LEFT JOIN customers c ON ro.customer_id = c.id
                LEFT JOIN vehicles v ON ro.vehicle_id = v.id
                LEFT JOIN employees t ON ro.technician_id = t.id
                LEFT JOIN employees p ON ro.painter_id = p.id
                WHERE ro.status NOT IN ('closed', 'delivered')
                ORDER BY ro.priority DESC, ro.target_delivery_date ASC
            """).fetchall())

            # Get latest movement for each RO to determine current department
            for ro in ros:
                last_move = db.execute("""
                    SELECT to_department, moved_at
                    FROM vehicle_movements
                    WHERE ro_id = ?
                    ORDER BY moved_at DESC LIMIT 1
                """, (ro["id"],)).fetchone()
                if last_move:
                    ro["current_department"] = last_move[0]
                    ro["last_move_time"] = last_move[1]
                else:
                    ro["current_department"] = "lot"
                    ro["last_move_time"] = None

        # Organize by department
        board = {dept: [] for dept in self.DEPARTMENTS}
        for ro in ros:
            dept = ro.get("current_department", "lot")
            if dept in board:
                board[dept].append(ro)

        return board

    def get_vehicle_history(self, ro_id: int) -> list[dict]:
        """Get the full movement history for a vehicle/RO."""
        with get_db() as db:
            rows = db.execute("""
                SELECT vm.*, e.first_name, e.last_name
                FROM vehicle_movements vm
                LEFT JOIN employees e ON vm.moved_by = e.id
                WHERE vm.ro_id = ?
                ORDER BY vm.moved_at ASC
            """, (ro_id,)).fetchall()
        return rows_to_list(rows)

    def move_vehicle(self, ro_id: int, to_department: str,
                     moved_by: int = None, notes: str = None) -> int:
        """
        Move a vehicle to a new department.

        Args:
            ro_id: Repair order ID
            to_department: Target department
            moved_by: Employee ID who moved it
            notes: Optional notes

        Returns:
            Movement record ID
        """
        if to_department not in self.DEPARTMENTS:
            raise ValueError(f"Invalid department: {to_department}. "
                           f"Valid: {', '.join(self.DEPARTMENTS)}")

        with get_db() as db:
            # Verify RO exists
            ro = db.execute("SELECT id FROM repair_orders WHERE id = ?", (ro_id,)).fetchone()
            if not ro:
                raise ValueError(f"Repair order {ro_id} not found")

            # Get current department
            last = db.execute("""
                SELECT to_department FROM vehicle_movements
                WHERE ro_id = ? ORDER BY moved_at DESC LIMIT 1
            """, (ro_id,)).fetchone()
            from_dept = last[0] if last else "lot"

            if from_dept == to_department:
                raise ValueError(f"Vehicle is already in {to_department}")

            # Insert movement record
            cur = db.execute("""
                INSERT INTO vehicle_movements (ro_id, from_department, to_department, moved_by, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (ro_id, from_dept, to_department, moved_by, notes))
            db.commit()

            # Auto-update RO status based on department
            status_map = {
                "lot": "open",
                "body": "in_progress",
                "frame": "in_progress",
                "mechanical": "in_progress",
                "paint": "in_progress",
                "detail": "in_progress",
                "assembly": "in_progress",
                "glass": "in_progress",
                "qa": "in_progress",
                "ready": "completed",
                "delivered": "delivered",
            }
            new_status = status_map.get(to_department)
            if new_status:
                db.execute("UPDATE repair_orders SET status = ? WHERE id = ?",
                          (new_status, ro_id))
                if to_department == "delivered":
                    db.execute(
                        "UPDATE repair_orders SET delivered_date = date('now') WHERE id = ?",
                        (ro_id,))
                elif to_department == "ready":
                    db.execute(
                        "UPDATE repair_orders SET actual_complete_date = date('now') WHERE id = ?",
                        (ro_id,))
                db.commit()

            return cur.lastrowid

    def get_my_jobs(self, employee_id: int) -> list[dict]:
        """Get all ROs assigned to a specific technician/painter."""
        with get_db() as db:
            ros = rows_to_list(db.execute("""
                SELECT ro.id, ro.ro_number, ro.status, ro.priority,
                       ro.target_delivery_date, ro.notes,
                       c.first_name, c.last_name, c.company_name,
                       v.year, v.make, v.model, v.color, v.license_plate, v.vin
                FROM repair_orders ro
                LEFT JOIN customers c ON ro.customer_id = c.id
                LEFT JOIN vehicles v ON ro.vehicle_id = v.id
                WHERE (ro.technician_id = ? OR ro.painter_id = ?)
                AND ro.status NOT IN ('closed', 'delivered')
                ORDER BY ro.priority DESC, ro.target_delivery_date ASC
            """, (employee_id, employee_id)).fetchall())

            for ro in ros:
                last_move = db.execute("""
                    SELECT to_department FROM vehicle_movements
                    WHERE ro_id = ? ORDER BY moved_at DESC LIMIT 1
                """, (ro["id"],)).fetchone()
                ro["current_department"] = last_move[0] if last_move else "lot"

                # Get lines assigned to this tech
                ro["my_lines"] = rows_to_list(db.execute("""
                    SELECT * FROM ro_lines
                    WHERE ro_id = ? AND (assigned_tech_id = ? OR assigned_tech_id IS NULL)
                    ORDER BY line_number
                """, (ro["id"], employee_id)).fetchall())

        return ros
