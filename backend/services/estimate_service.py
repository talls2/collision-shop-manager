"""
EstimateService: Business logic for estimate management.
Encapsulates validation, numbering, and line item management.
Delegates data access to EstimateRepository and RepairOrderRepository.
"""
from repositories.estimate_repository import EstimateRepository
from repositories.repair_order_repository import RepairOrderRepository


class EstimateService:
    """Service for managing estimates with totals and conversions."""

    def __init__(self):
        self.estimate_repo = EstimateRepository()
        self.ro_repo = RepairOrderRepository()

    def list_estimates(self, status: str | None = None, search: str | None = None) -> list[dict]:
        """
        List estimates with optional status and search filtering.

        Args:
            status: Filter by estimate status (e.g., 'pending', 'accepted', 'converted')
            search: Search term to filter by customer name or vehicle info

        Returns:
            List of estimate dictionaries with customer and vehicle info
        """
        return self.estimate_repo.list_with_details(status=status, search=search)

    def get_estimate(self, estimate_id: int) -> dict | None:
        """
        Get a complete estimate with all details (customer, vehicle, lines, etc.).

        Args:
            estimate_id: Estimate ID

        Returns:
            Estimate dictionary with all related data or None if not found
        """
        return self.estimate_repo.get_full(estimate_id)

    def create_estimate(self, data: dict) -> int:
        """
        Create a new estimate with auto-generated estimate number.

        Args:
            data: Estimate data dict (estimate_number will be auto-generated)

        Returns:
            New estimate ID

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not data.get("customer_id"):
            raise ValueError("Estimate must have a customer_id")

        # Auto-generate estimate number
        data["estimate_number"] = self.estimate_repo.next_number()

        # Set default status if not provided
        if "status" not in data:
            data["status"] = "pending"

        return self.estimate_repo.insert(data)

    def update_estimate(self, estimate_id: int, data: dict) -> None:
        """
        Update an existing estimate.

        Args:
            estimate_id: Estimate ID
            data: Updated estimate data

        Raises:
            ValueError: If estimate not found
        """
        existing = self.estimate_repo.get_by_id(estimate_id)
        if not existing:
            raise ValueError(f"Estimate {estimate_id} not found")

        # Auto-stamp closed_date when an estimate moves to a terminal status.
        new_status = data.get("status")
        terminal = {"converted", "rejected", "approved"}
        if new_status in terminal and not existing.get("closed_date") and "closed_date" not in data:
            from datetime import date
            data["closed_date"] = date.today().isoformat()

        self.estimate_repo.update(estimate_id, data)

        # If tax_exempt was toggled, totals need to be recomputed.
        if "tax_exempt" in data:
            self.estimate_repo.recalc_totals(estimate_id)

    def add_line(self, estimate_id: int, data: dict) -> int:
        """
        Add a line item to an estimate and recalculate totals.

        Args:
            estimate_id: Estimate ID
            data: Line item data (labor_hours, labor_rate, parts_cost, paint_cost, other_cost, description)

        Returns:
            New line item ID

        Raises:
            ValueError: If estimate not found
        """
        # Verify estimate exists
        existing = self.estimate_repo.get_by_id(estimate_id)
        if not existing:
            raise ValueError(f"Estimate {estimate_id} not found")

        # Default `taxable`: parts are taxable, everything else is not — caller can override.
        if data.get("taxable") is None:
            data["taxable"] = 1 if data.get("line_type") == "part" else 0

        # Add the line
        line_id = self.estimate_repo.add_line(estimate_id, data)

        # Recalculate totals
        self.estimate_repo.recalc_totals(estimate_id)

        return line_id

    def delete_line(self, estimate_id: int, line_id: int) -> None:
        """
        Delete a line item from an estimate and recalculate totals.

        Args:
            estimate_id: Estimate ID
            line_id: Line item ID

        Raises:
            ValueError: If estimate not found
        """
        # Verify estimate exists
        existing = self.estimate_repo.get_by_id(estimate_id)
        if not existing:
            raise ValueError(f"Estimate {estimate_id} not found")

        # Delete the line
        self.estimate_repo.delete_line(estimate_id, line_id)

        # Recalculate totals
        self.estimate_repo.recalc_totals(estimate_id)

    def update_line(self, estimate_id: int, line_id: int, data: dict) -> None:
        """Update fields on an estimate line, recompute line_total, refresh document."""
        existing = self.estimate_repo.get_by_id(estimate_id)
        if not existing:
            raise ValueError(f"Estimate {estimate_id} not found")
        from config.database import get_db
        allowed = {"taxable", "operation", "description", "part_number", "part_type",
                   "quantity", "labor_hours", "labor_rate", "paint_hours", "paint_rate",
                   "part_price", "part_cost", "notes"}
        clean = {k: v for k, v in data.items() if k in allowed and v is not None}
        if "taxable" in clean:
            clean["taxable"] = 1 if clean["taxable"] else 0
        if not clean:
            return
        with get_db() as db:
            set_clause = ", ".join(f"{k} = ?" for k in clean)
            db.execute(
                f"UPDATE estimate_lines SET {set_clause} WHERE id = ? AND estimate_id = ?",
                (*clean.values(), line_id, estimate_id),
            )
            row = db.execute("SELECT * FROM estimate_lines WHERE id = ?", (line_id,)).fetchone()
            if row:
                lh = float(row["labor_hours"] or 0)
                lr = float(row["labor_rate"] or 0)
                ph = float(row["paint_hours"] or 0)
                pr = float(row["paint_rate"] or 0)
                pp = float(row["part_price"] or 0)
                qty = float(row["quantity"] or 1)
                line_total = round((lh * lr) + (ph * pr) + (pp * qty), 2)
                db.execute("UPDATE estimate_lines SET line_total = ? WHERE id = ?", (line_total, line_id))
            db.commit()
        self.estimate_repo.recalc_totals(estimate_id)

    def delete_estimate(self, estimate_id: int) -> None:
        """
        Delete an estimate.

        Refuses if the estimate has been converted to a Repair Order (deleting
        would orphan the RO's reference). Cascades to estimate_lines via FK.

        Raises:
            ValueError: If the estimate doesn't exist, was converted, or has
                        any RO referencing it.
        """
        existing = self.estimate_repo.get_by_id(estimate_id)
        if not existing:
            raise ValueError(f"Estimate {estimate_id} not found")

        from config.database import get_db
        with get_db() as db:
            ros = db.execute(
                "SELECT COUNT(*) AS n FROM repair_orders WHERE estimate_id = ?",
                (estimate_id,),
            ).fetchone()["n"]
            if ros:
                raise ValueError(
                    f"Cannot delete this estimate — it has been converted to "
                    f"{ros} repair order(s). Delete the RO first if you really "
                    f"want to remove the estimate."
                )
            db.execute("DELETE FROM estimates WHERE id = ?", (estimate_id,))
            db.commit()

    def move_line(self, estimate_id: int, line_id: int, direction: str) -> None:
        """Swap a line's line_number with its neighbor (up or down)."""
        if direction not in ("up", "down"):
            raise ValueError("direction must be 'up' or 'down'")
        from config.database import get_db
        with get_db() as db:
            rows = db.execute(
                "SELECT id, line_number FROM estimate_lines WHERE estimate_id = ? ORDER BY line_number",
                (estimate_id,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            nums = [r["line_number"] for r in rows]
            if line_id not in ids:
                raise ValueError(f"Line {line_id} not on estimate {estimate_id}")
            idx = ids.index(line_id)
            target = idx - 1 if direction == "up" else idx + 1
            if target < 0 or target >= len(ids):
                return
            db.execute("UPDATE estimate_lines SET line_number = ? WHERE id = ?", (nums[target], ids[idx]))
            db.execute("UPDATE estimate_lines SET line_number = ? WHERE id = ?", (nums[idx], ids[target]))
            db.commit()

    def convert_to_ro(self, estimate_id: int, team: list[dict] | None = None) -> int:
        """
        Convert an estimate to a repair order.
        Creates a new RO with all estimate data and lines copied over.
        Marks the estimate as 'converted'.

        Args:
            estimate_id: Estimate ID to convert
            team: Optional list of {employee_id, role} dicts to assign as the
                  initial RO team. At least one entry IS REQUIRED — every RO
                  needs someone assigned to it (a worker, an estimator, etc.).

        Returns:
            New repair order ID

        Raises:
            ValueError: If estimate not found, already converted, or no team
                        provided.
        """
        # Get full estimate data
        estimate = self.estimate_repo.get_full(estimate_id)
        if not estimate:
            raise ValueError(f"Estimate {estimate_id} not found")

        if estimate.get("status") == "converted":
            raise ValueError(f"Estimate {estimate_id} is already converted")

        # Require at least one worker on the team. The estimator from the
        # estimate counts as a fallback — they're already on the record.
        team = team or []
        valid_team = [t for t in team if t.get("employee_id") and (t.get("role") or "").strip()]
        if not valid_team and not estimate.get("estimator_id"):
            raise ValueError(
                "At least one worker must be assigned before converting to a repair order. "
                "Pick at least one worker (technician, painter, body tech, etc.) and a role."
            )

        # Prepare RO data from estimate
        ro_data = {
            "customer_id": estimate.get("customer_id"),
            "vehicle_id": estimate.get("vehicle_id"),
            "insurance_company_id": estimate.get("insurance_company_id"),
            "estimator_id": estimate.get("estimator_id"),
            "estimate_id": estimate_id,
            "ro_number": self.ro_repo.next_number(),
            "claim_number": estimate.get("claim_number"),
            "policy_number": estimate.get("policy_number"),
            "deductible": estimate.get("deductible", 0),
            "loss_date": estimate.get("loss_date"),
            "status": "open",
            "subtotal_labor": estimate.get("subtotal_labor", 0),
            "subtotal_parts": estimate.get("subtotal_parts", 0),
            "subtotal_paint": estimate.get("subtotal_paint", 0),
            "subtotal_other": estimate.get("subtotal_other", 0),
            "tax_amount": estimate.get("tax_amount", 0),
            "tax_exempt": estimate.get("tax_exempt", 0),
            "total_amount": estimate.get("total_amount", 0),
            "balance_due": estimate.get("total_amount", 0),
        }

        # Create the RO
        ro_id = self.ro_repo.insert(ro_data)

        # Copy all estimate lines to RO lines (including taxable flag)
        if estimate.get("lines"):
            for line in estimate["lines"]:
                ro_line_data = {
                    "line_type": line.get("line_type", "labor"),
                    "operation": line.get("operation"),
                    "description": line.get("description"),
                    "part_number": line.get("part_number"),
                    "part_type": line.get("part_type"),
                    "quantity": line.get("quantity", 1),
                    "labor_hours": line.get("labor_hours", 0),
                    "labor_rate": line.get("labor_rate", 0),
                    "paint_hours": line.get("paint_hours", 0),
                    "paint_rate": line.get("paint_rate", 0),
                    "part_price": line.get("part_price", 0),
                    "part_cost": line.get("part_cost", 0),
                    "taxable": line.get("taxable", 1 if line.get("line_type") == "part" else 0),
                }
                self.ro_repo.add_line(ro_id, ro_line_data)

        # Recompute totals so any tax-rate change since the estimate is reflected.
        self.ro_repo.recalc_totals(ro_id)

        # Seed the RO team:
        # 1. The estimator from the estimate (always added if set) — recorded as 'estimator' role.
        # 2. Any team members the user explicitly chose at conversion time.
        from config.database import get_db
        with get_db() as db:
            if estimate.get("estimator_id"):
                db.execute(
                    "INSERT INTO ro_assignments (ro_id, employee_id, role) VALUES (?, ?, ?)",
                    (ro_id, estimate["estimator_id"], "estimator"),
                )
            for member in valid_team:
                db.execute(
                    "INSERT INTO ro_assignments (ro_id, employee_id, role) VALUES (?, ?, ?)",
                    (ro_id, int(member["employee_id"]), member["role"].strip()),
                )
            db.commit()

        # Mark estimate as converted + stamp the closed date.
        from datetime import date
        self.estimate_repo.update(estimate_id, {
            "status": "converted",
            "closed_date": date.today().isoformat(),
        })

        return {"id": ro_id, "ro_number": ro_data["ro_number"], "message": "Repair order created from estimate"}
