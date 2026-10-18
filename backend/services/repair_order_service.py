"""
RepairOrderService: Business logic for repair order management.
Encapsulates validation, numbering, line items, payments, and status management.
Delegates data access to RepairOrderRepository and PaymentRepository.
"""
from repositories.repair_order_repository import RepairOrderRepository
from repositories.payment_repository import PaymentRepository


class RepairOrderService:
    """Service for managing repair orders with totals and payments."""

    def __init__(self):
        self.repo = RepairOrderRepository()
        self.payment_repo = PaymentRepository()

    def list_ros(self, status: str | None = None, search: str | None = None, assigned_to: int | None = None) -> list[dict]:
        """
        List repair orders with optional status and search filtering.

        Args:
            status: Filter by RO status (e.g., 'open', 'in_progress', 'completed', 'closed')
            search: Search term to filter by customer name or vehicle info

        Returns:
            List of repair order dictionaries with customer and vehicle info
        """
        return self.repo.list_with_details(status=status, search=search, assigned_to=assigned_to)

    def get_ro(self, ro_id: int) -> dict | None:
        """
        Get a complete repair order with all details (customer, vehicle, lines, payments, timecards, schedule).

        Args:
            ro_id: Repair order ID

        Returns:
            Repair order dictionary with all related data or None if not found
        """
        return self.repo.get_full(ro_id)

    def create_ro(self, data: dict) -> int:
        """
        Create a new repair order with auto-generated RO number.

        Args:
            data: Repair order data dict (repair_order_number will be auto-generated)

        Returns:
            New repair order ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not data.get("customer_id"):
            raise ValueError("Repair order must have a customer_id")

        # Auto-generate RO number
        data["ro_number"] = self.repo.next_number()

        # Set default status and amounts if not provided
        if "status" not in data:
            data["status"] = "open"
        if "amount_paid" not in data:
            data["amount_paid"] = 0
        if "balance_due" not in data:
            data["balance_due"] = 0

        return self.repo.insert(data)

    def update_ro(self, ro_id: int, data: dict) -> None:
        """
        Update an existing repair order.

        Args:
            ro_id: Repair order ID
            data: Updated repair order data

        Raises:
            ValueError: If repair order not found
        """
        existing = self.repo.get_by_id(ro_id)
        if not existing:
            raise ValueError(f"Repair order {ro_id} not found")

        self.repo.update(ro_id, data)

        # If tax_exempt was toggled, totals need to be recomputed.
        if "tax_exempt" in data:
            self.repo.recalc_totals(ro_id)

    def add_line(self, ro_id: int, data: dict) -> int:
        """
        Add a line item to a repair order and recalculate totals.

        Args:
            ro_id: Repair order ID
            data: Line item data (labor_hours, labor_rate, parts_cost, paint_cost, other_cost, description, vendor_id)

        Returns:
            New line item ID

        Raises:
            ValueError: If repair order not found
        """
        # Verify RO exists
        existing = self.repo.get_by_id(ro_id)
        if not existing:
            raise ValueError(f"Repair order {ro_id} not found")

        # Default `taxable`: parts are taxable, everything else is not — caller can override.
        if data.get("taxable") is None:
            data["taxable"] = 1 if data.get("line_type") == "part" else 0

        # Lines added AFTER an RO already has lines (i.e. after conversion from
        # estimate) are supplements — additional damage/work found during repair.
        # Auto-flag them so they show as supplements on invoices/reports, unless
        # the caller explicitly says otherwise.
        if not data.get("is_supplement"):
            from config.database import get_db
            with get_db() as db:
                stats = db.execute(
                    "SELECT COUNT(*) AS n, COALESCE(MAX(supplement_number), 0) AS m FROM ro_lines WHERE ro_id = ?",
                    (ro_id,),
                ).fetchone()
            existing_lines = stats["n"] if stats else 0
            current_max_supp = stats["m"] if stats else 0
            if existing_lines > 0:
                data["is_supplement"] = 1
                # Default to current supplement number (or 1 if none yet); admin
                # can bump this manually for a new round of insurance approval.
                if not data.get("supplement_number"):
                    data["supplement_number"] = max(1, current_max_supp)

        # Add the line
        line_id = self.repo.add_line(ro_id, data)

        # Recalculate totals
        self.repo.recalc_totals(ro_id)

        return line_id

    def delete_line(self, ro_id: int, line_id: int) -> None:
        """Delete a line item from an RO and recompute totals."""
        existing = self.repo.get_by_id(ro_id)
        if not existing:
            raise ValueError(f"Repair order {ro_id} not found")
        from config.database import get_db
        with get_db() as db:
            db.execute("DELETE FROM ro_lines WHERE id = ? AND ro_id = ?", (line_id, ro_id))
            db.commit()
        self.repo.recalc_totals(ro_id)

    def update_line(self, ro_id: int, line_id: int, data: dict) -> None:
        """Update fields on an RO line, recompute its line_total, and refresh document totals."""
        from config.database import get_db
        allowed = {"taxable", "operation", "description", "part_number", "part_type",
                   "quantity", "labor_hours", "labor_rate", "paint_hours", "paint_rate",
                   "part_price", "part_cost", "status", "notes"}
        clean = {k: v for k, v in data.items() if k in allowed and v is not None}
        if "taxable" in clean:
            clean["taxable"] = 1 if clean["taxable"] else 0
        if "status" in clean:
            allowed_statuses = {"pending", "ordered", "received", "installed", "complete"}
            if clean["status"] not in allowed_statuses:
                raise ValueError(f"Invalid line status: {clean['status']}")
        if not clean:
            return
        with get_db() as db:
            # Apply the field updates
            set_clause = ", ".join(f"{k} = ?" for k in clean)
            db.execute(
                f"UPDATE ro_lines SET {set_clause} WHERE id = ? AND ro_id = ?",
                (*clean.values(), line_id, ro_id),
            )
            # Recompute this line's line_total from its current values
            row = db.execute("SELECT * FROM ro_lines WHERE id = ?", (line_id,)).fetchone()
            if row:
                lh = float(row["labor_hours"] or 0)
                lr = float(row["labor_rate"] or 0)
                ph = float(row["paint_hours"] or 0)
                pr = float(row["paint_rate"] or 0)
                pp = float(row["part_price"] or 0)
                qty = float(row["quantity"] or 1)
                line_total = round((lh * lr) + (ph * pr) + (pp * qty), 2)
                db.execute("UPDATE ro_lines SET line_total = ? WHERE id = ?", (line_total, line_id))
            db.commit()
        self.repo.recalc_totals(ro_id)

    def move_line(self, ro_id: int, line_id: int, direction: str) -> None:
        """Swap a line's line_number with its neighbor (up or down)."""
        if direction not in ("up", "down"):
            raise ValueError("direction must be 'up' or 'down'")
        from config.database import get_db
        with get_db() as db:
            rows = db.execute(
                "SELECT id, line_number FROM ro_lines WHERE ro_id = ? ORDER BY line_number",
                (ro_id,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            nums = [r["line_number"] for r in rows]
            if line_id not in ids:
                raise ValueError(f"Line {line_id} not on RO {ro_id}")
            idx = ids.index(line_id)
            target = idx - 1 if direction == "up" else idx + 1
            if target < 0 or target >= len(ids):
                return  # already at the end — no-op
            # Swap line_numbers between idx and target. SQLite is happy because
            # there's no unique constraint on (ro_id, line_number).
            db.execute("UPDATE ro_lines SET line_number = ? WHERE id = ?", (nums[target], ids[idx]))
            db.execute("UPDATE ro_lines SET line_number = ? WHERE id = ?", (nums[idx], ids[target]))
            db.commit()

    def add_payment(self, ro_id: int, data: dict) -> int:
        """
        Add a payment to a repair order and recalculate totals/balance.

        Args:
            ro_id: Repair order ID
            data: Payment data (amount, payment_date, payment_method, notes)

        Returns:
            New payment ID

        Raises:
            ValueError: If repair order not found or amount invalid
        """
        # Verify RO exists
        existing = self.repo.get_by_id(ro_id)
        if not existing:
            raise ValueError(f"Repair order {ro_id} not found")

        # Validate payment amount
        if not data.get("amount"):
            raise ValueError("Payment must have an amount")

        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")

        # Add payment using payment repository
        payment_id = self.payment_repo.add_payment(ro_id, data)

        # Recalculate totals (updates amount_paid and balance_due)
        self.repo.recalc_totals(ro_id)

        return payment_id

    def delete_payment(self, ro_id: int, payment_id: int) -> dict:
        """
        Void (delete) a payment on a repair order.

        Works even when the RO is closed — the secretary might discover a
        wrong entry weeks later. After deleting, amount_paid and balance_due
        are recomputed so the RO reflects the corrected total.

        Args:
            ro_id: Repair order ID (used for authorization / consistency check)
            payment_id: Payment row ID to delete

        Returns:
            Dict with the RO's new amount_paid and balance_due.

        Raises:
            ValueError: If the RO or payment doesn't exist, or the payment
                        doesn't belong to this RO.
        """
        # Verify the RO exists at all
        ro = self.repo.get_by_id(ro_id)
        if not ro:
            raise ValueError(f"Repair order {ro_id} not found")

        # Verify the payment exists AND belongs to this RO — protects against
        # rogue calls that try to delete another RO's payment by guessing IDs.
        pay = self.payment_repo.get_payment(payment_id)
        if not pay:
            raise ValueError(f"Payment {payment_id} not found")
        if int(pay.get("ro_id") or 0) != int(ro_id):
            raise ValueError(f"Payment {payment_id} does not belong to RO {ro_id}")

        deleted = self.payment_repo.delete_payment(payment_id)
        if not deleted:
            raise ValueError(f"Payment {payment_id} could not be deleted")

        # Recompute totals — flips balance_due back up if this was a real payment
        self.repo.recalc_totals(ro_id)

        # Return the refreshed money numbers so the client can update in place
        refreshed = self.repo.get_by_id(ro_id) or {}
        return {
            "deleted_payment_id": payment_id,
            "amount_paid": refreshed.get("amount_paid", 0),
            "balance_due": refreshed.get("balance_due", 0),
        }

    # ── Team assignments ──
    def list_team(self, ro_id: int) -> list[dict]:
        """Return the list of (employee, role) assignments for an RO, with employee names."""
        from config.database import get_db
        with get_db() as db:
            rows = db.execute(
                """SELECT a.id, a.ro_id, a.employee_id, a.role, a.notes, a.assigned_at,
                          e.first_name, e.last_name, e.employee_code
                   FROM ro_assignments a
                   LEFT JOIN employees e ON e.id = a.employee_id
                   WHERE a.ro_id = ?
                   ORDER BY a.assigned_at""",
                (ro_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_team_member(self, ro_id: int, employee_id: int, role: str, notes: str | None = None) -> int:
        """Add an employee to an RO's team with a role label (free text)."""
        existing = self.repo.get_by_id(ro_id)
        if not existing:
            raise ValueError(f"Repair order {ro_id} not found")
        if not employee_id:
            raise ValueError("employee_id is required")
        if not role or not role.strip():
            raise ValueError("role is required")
        from config.database import get_db
        with get_db() as db:
            cur = db.execute(
                "INSERT INTO ro_assignments (ro_id, employee_id, role, notes) VALUES (?, ?, ?, ?)",
                (ro_id, int(employee_id), role.strip(), notes),
            )
            db.commit()
            return cur.lastrowid

    def remove_team_member(self, ro_id: int, assignment_id: int) -> None:
        """Remove a single team member assignment."""
        from config.database import get_db
        with get_db() as db:
            db.execute(
                "DELETE FROM ro_assignments WHERE id = ? AND ro_id = ?",
                (assignment_id, ro_id),
            )
            db.commit()

    def update_status(self, ro_id: int, new_status: str) -> None:
        """
        Update the status of a repair order, auto-stamping the corresponding
        milestone date if it isn't already set.

        Args:
            ro_id: Repair order ID
            new_status: 'open', 'in_progress', 'on_hold', 'completed', 'delivered', 'closed'

        Raises:
            ValueError: If repair order not found
        """
        existing = self.repo.get_by_id(ro_id)
        if not existing:
            raise ValueError(f"Repair order {ro_id} not found")

        from datetime import date
        today = date.today().isoformat()

        # Map status → date column to auto-stamp on transition.
        date_col_map = {
            "in_progress": "repair_start_date",
            "completed":   "actual_complete_date",
            "delivered":   "delivered_date",
            "closed":      "closed_date",
        }

        update = {"status": new_status}
        col = date_col_map.get(new_status)
        if col and not existing.get(col):
            update[col] = today

        self.repo.update(ro_id, update)
