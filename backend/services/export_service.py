"""
ExportService: Generate QuickBooks IIF, generic XML, and Mitchell Connect XML exports.
"""
import io
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString
from config.database import get_db, row_to_dict, rows_to_list


class ExportService:
    """Handles all export file generation."""

    # ──────────────────────────────────────────────────
    # QUICKBOOKS IIF EXPORT
    # ──────────────────────────────────────────────────
    def export_quickbooks_iif(self, date_from: str = None, date_to: str = None) -> str:
        """
        Export closed repair orders as QuickBooks IIF (Intuit Interchange Format).
        IIF is a tab-delimited format QuickBooks can import directly.

        Args:
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)

        Returns:
            IIF file content as string
        """
        with get_db() as db:
            query = """
                SELECT ro.*, c.first_name, c.last_name, c.company_name,
                       v.year, v.make, v.model, v.vin
                FROM repair_orders ro
                LEFT JOIN customers c ON ro.customer_id = c.id
                LEFT JOIN vehicles v ON ro.vehicle_id = v.id
                WHERE 1=1
            """
            params = []
            if date_from:
                query += " AND ro.create_date >= ?"
                params.append(date_from)
            if date_to:
                query += " AND ro.create_date <= ?"
                params.append(date_to)
            query += " ORDER BY ro.create_date"

            ros = rows_to_list(db.execute(query, params).fetchall())

            # Get payments for these ROs
            ro_ids = [ro["id"] for ro in ros]
            payments = []
            if ro_ids:
                placeholders = ",".join("?" * len(ro_ids))
                payments = rows_to_list(db.execute(
                    f"SELECT * FROM payments WHERE ro_id IN ({placeholders})",
                    ro_ids
                ).fetchall())

        lines = []

        # ── Header: Invoice transactions ──
        lines.append("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tMEMO\tAMOUNT\tDOCNUM")
        lines.append("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tMEMO\tAMOUNT\tDOCNUM")
        lines.append("!ENDTRNS")

        for ro in ros:
            cust_name = ro.get("company_name") or \
                f"{ro.get('first_name', '')} {ro.get('last_name', '')}".strip() or "Customer"
            ro_num = ro.get("ro_number", "")
            ro_date = ro.get("create_date", "")
            try:
                dt = datetime.strptime(ro_date[:10], "%Y-%m-%d")
                iif_date = dt.strftime("%m/%d/%Y")
            except Exception:
                iif_date = ro_date

            total = float(ro.get("total_amount", 0) or 0)
            memo = f"RO {ro_num}"
            veh_desc = f"{ro.get('year', '')} {ro.get('make', '')} {ro.get('model', '')}".strip()
            if veh_desc:
                memo += f" - {veh_desc}"

            # Main transaction line (Accounts Receivable debit)
            lines.append(f"TRNS\tINVOICE\t{iif_date}\tAccounts Receivable\t{cust_name}\t{memo}\t{total:.2f}\t{ro_num}")

            # Split lines by category
            labor = float(ro.get("subtotal_labor", 0) or 0)
            parts = float(ro.get("subtotal_parts", 0) or 0)
            paint = float(ro.get("subtotal_paint", 0) or 0)
            sublet = float(ro.get("subtotal_sublet", 0) or 0)
            other = float(ro.get("subtotal_other", 0) or 0)
            tax = float(ro.get("tax_amount", 0) or 0)

            if labor > 0:
                lines.append(f"SPL\tINVOICE\t{iif_date}\tBody Labor Income\t{cust_name}\t{memo}\t{-labor:.2f}\t{ro_num}")
            if parts > 0:
                lines.append(f"SPL\tINVOICE\t{iif_date}\tParts Income\t{cust_name}\t{memo}\t{-parts:.2f}\t{ro_num}")
            if paint > 0:
                lines.append(f"SPL\tINVOICE\t{iif_date}\tPaint Labor Income\t{cust_name}\t{memo}\t{-paint:.2f}\t{ro_num}")
            if sublet > 0:
                lines.append(f"SPL\tINVOICE\t{iif_date}\tSublet Income\t{cust_name}\t{memo}\t{-sublet:.2f}\t{ro_num}")
            if other > 0:
                lines.append(f"SPL\tINVOICE\t{iif_date}\tOther Income\t{cust_name}\t{memo}\t{-other:.2f}\t{ro_num}")
            if tax > 0:
                lines.append(f"SPL\tINVOICE\t{iif_date}\tSales Tax Payable\t{cust_name}\t{memo}\t{-tax:.2f}\t{ro_num}")

            lines.append("ENDTRNS")

        # ── Payments as PAYMENT transactions ──
        for pmt in payments:
            ro_match = next((r for r in ros if r["id"] == pmt["ro_id"]), None)
            if not ro_match:
                continue
            cust_name = ro_match.get("company_name") or \
                f"{ro_match.get('first_name', '')} {ro_match.get('last_name', '')}".strip() or "Customer"

            pmt_date = pmt.get("payment_date", "")
            try:
                dt = datetime.strptime(pmt_date[:10], "%Y-%m-%d")
                iif_date = dt.strftime("%m/%d/%Y")
            except Exception:
                iif_date = pmt_date

            amount = float(pmt.get("amount", 0) or 0)
            method = (pmt.get("payment_method", "") or "").replace("_", " ").title()
            ref = pmt.get("reference_number", "")

            # Payment transaction
            deposit_acct = "Undeposited Funds"
            if method in ("Check", "Insurance"):
                deposit_acct = "Undeposited Funds"
            elif method in ("Credit Card", "Debit"):
                deposit_acct = "Undeposited Funds"
            elif method == "Cash":
                deposit_acct = "Cash on Hand"

            memo = f"Payment {ro_match.get('ro_number', '')} {ref}".strip()
            lines.append(f"TRNS\tPAYMENT\t{iif_date}\t{deposit_acct}\t{cust_name}\t{memo}\t{amount:.2f}\t{ref}")
            lines.append(f"SPL\tPAYMENT\t{iif_date}\tAccounts Receivable\t{cust_name}\t{memo}\t{-amount:.2f}\t{ref}")
            lines.append("ENDTRNS")

        return "\n".join(lines)

    # ──────────────────────────────────────────────────
    # GENERIC XML EXPORT
    # ──────────────────────────────────────────────────
    def export_xml(self, date_from: str = None, date_to: str = None) -> str:
        """
        Export repair orders, payments, and line items as generic XML.
        Compatible with various accounting systems.
        """
        with get_db() as db:
            query = """
                SELECT ro.*, c.first_name, c.last_name, c.company_name,
                       c.address, c.city, c.state, c.zip_code, c.phone_home, c.email,
                       v.year, v.make, v.model, v.vin, v.color, v.license_plate,
                       ic.company_name AS insurance_name
                FROM repair_orders ro
                LEFT JOIN customers c ON ro.customer_id = c.id
                LEFT JOIN vehicles v ON ro.vehicle_id = v.id
                LEFT JOIN insurance_companies ic ON ro.insurance_company_id = ic.id
                WHERE 1=1
            """
            params = []
            if date_from:
                query += " AND ro.create_date >= ?"
                params.append(date_from)
            if date_to:
                query += " AND ro.create_date <= ?"
                params.append(date_to)
            query += " ORDER BY ro.create_date"
            ros = rows_to_list(db.execute(query, params).fetchall())

            # Get lines and payments for each RO
            for ro in ros:
                ro["lines"] = rows_to_list(db.execute(
                    "SELECT * FROM ro_lines WHERE ro_id = ? ORDER BY line_number",
                    (ro["id"],)
                ).fetchall())
                ro["payments"] = rows_to_list(db.execute(
                    "SELECT * FROM payments WHERE ro_id = ? ORDER BY payment_date",
                    (ro["id"],)
                ).fetchall())

            # Get shop info
            shop = row_to_dict(db.execute("SELECT * FROM body_shop LIMIT 1").fetchone())

        root = Element("ShopManagerExport")
        root.set("version", "1.0")
        root.set("exported_at", datetime.now().isoformat())

        # Shop info
        if shop:
            shop_el = SubElement(root, "Shop")
            for key in ["shop_name", "address", "city", "state", "zip_code", "phone", "email", "tax_id"]:
                if shop.get(key):
                    SubElement(shop_el, key).text = str(shop[key])

        # Repair orders
        orders_el = SubElement(root, "RepairOrders")
        for ro in ros:
            ro_el = SubElement(orders_el, "RepairOrder")
            ro_el.set("id", str(ro["id"]))
            ro_el.set("number", ro.get("ro_number", ""))

            # RO fields
            for key in ["status", "create_date", "claim_number", "policy_number",
                         "deductible", "subtotal_labor", "subtotal_parts", "subtotal_paint",
                         "subtotal_sublet", "subtotal_other", "tax_amount", "total_amount",
                         "amount_paid", "balance_due"]:
                val = ro.get(key)
                if val is not None:
                    SubElement(ro_el, key).text = str(val)

            # Customer
            cust_el = SubElement(ro_el, "Customer")
            cust_name = ro.get("company_name") or \
                f"{ro.get('first_name', '')} {ro.get('last_name', '')}".strip()
            SubElement(cust_el, "name").text = cust_name
            for key in ["address", "city", "state", "zip_code", "phone_home", "email"]:
                if ro.get(key):
                    SubElement(cust_el, key).text = str(ro[key])

            # Vehicle
            veh_el = SubElement(ro_el, "Vehicle")
            for key in ["year", "make", "model", "vin", "color", "license_plate"]:
                if ro.get(key):
                    SubElement(veh_el, key).text = str(ro[key])

            # Insurance
            if ro.get("insurance_name"):
                ins_el = SubElement(ro_el, "Insurance")
                SubElement(ins_el, "company_name").text = ro["insurance_name"]
                if ro.get("claim_number"):
                    SubElement(ins_el, "claim_number").text = ro["claim_number"]

            # Lines
            lines_el = SubElement(ro_el, "Lines")
            for line in ro.get("lines", []):
                line_el = SubElement(lines_el, "Line")
                line_el.set("number", str(line.get("line_number", "")))
                for key in ["line_type", "operation", "description", "part_number",
                             "part_type", "quantity", "labor_hours", "labor_rate",
                             "paint_hours", "paint_rate", "part_price", "part_cost",
                             "line_total"]:
                    val = line.get(key)
                    if val is not None:
                        SubElement(line_el, key).text = str(val)

            # Payments
            pmts_el = SubElement(ro_el, "Payments")
            for pmt in ro.get("payments", []):
                pmt_el = SubElement(pmts_el, "Payment")
                for key in ["payment_date", "amount", "payment_method",
                             "reference_number", "payer_type", "payer_name"]:
                    val = pmt.get(key)
                    if val is not None:
                        SubElement(pmt_el, key).text = str(val)

        raw = tostring(root, encoding="unicode")
        return parseString(raw).toprettyxml(indent="  ")

    # ──────────────────────────────────────────────────
    # MITCHELL CONNECT XML EXPORT
    # ──────────────────────────────────────────────────
    def export_mitchell_connect_xml(self, date_from: str = None, date_to: str = None) -> str:
        """
        Export estimates and repair orders in Mitchell Connect compatible XML format.
        This generates the XML file that can be imported into Mitchell Connect
        to populate estimate data (vehicle, damage, line items, totals).

        Format follows Mitchell's EMS (Estimate Management System) XML structure.
        """
        with get_db() as db:
            # Get estimates (Mitchell Connect primarily imports estimates)
            query = """
                SELECT e.*, c.first_name, c.last_name, c.company_name,
                       c.address, c.city, c.state, c.zip_code, c.phone_home, c.email,
                       v.year, v.make, v.model, v.submodel, v.vin, v.color,
                       v.license_plate, v.license_state, v.mileage, v.production_date,
                       ic.company_name AS insurance_name, ic.phone AS insurance_phone,
                       ic.address AS insurance_address
                FROM estimates e
                LEFT JOIN customers c ON e.customer_id = c.id
                LEFT JOIN vehicles v ON e.vehicle_id = v.id
                LEFT JOIN insurance_companies ic ON e.insurance_company_id = ic.id
                WHERE 1=1
            """
            params = []
            if date_from:
                query += " AND e.estimate_date >= ?"
                params.append(date_from)
            if date_to:
                query += " AND e.estimate_date <= ?"
                params.append(date_to)
            query += " ORDER BY e.estimate_date"
            estimates = rows_to_list(db.execute(query, params).fetchall())

            for est in estimates:
                est["lines"] = rows_to_list(db.execute(
                    "SELECT * FROM estimate_lines WHERE estimate_id = ? ORDER BY line_number",
                    (est["id"],)
                ).fetchall())

            shop = row_to_dict(db.execute("SELECT * FROM body_shop LIMIT 1").fetchone())

        root = Element("MitchellEstimateExport")
        root.set("version", "1.0")
        root.set("source", "ShopManager")
        root.set("exported_at", datetime.now().isoformat())

        for est in estimates:
            claim = SubElement(root, "Claim")

            # Claim info
            info = SubElement(claim, "ClaimInfo")
            SubElement(info, "ClaimNumber").text = est.get("claim_number", "")
            SubElement(info, "PolicyNumber").text = est.get("policy_number", "")
            SubElement(info, "LossDate").text = est.get("loss_date", "")
            SubElement(info, "Deductible").text = str(est.get("deductible", 0))

            # Estimate info
            est_el = SubElement(claim, "Estimate")
            SubElement(est_el, "EstimateNumber").text = est.get("estimate_number", "")
            SubElement(est_el, "EstimateDate").text = est.get("estimate_date", "")
            SubElement(est_el, "Status").text = est.get("status", "")
            SubElement(est_el, "PointOfImpact").text = est.get("point_of_impact", "")
            SubElement(est_el, "DamageDescription").text = est.get("damage_description", "")

            # Shop info
            if shop:
                shop_el = SubElement(claim, "RepairFacility")
                SubElement(shop_el, "Name").text = shop.get("shop_name", "")
                SubElement(shop_el, "Address").text = shop.get("address", "")
                SubElement(shop_el, "City").text = shop.get("city", "")
                SubElement(shop_el, "State").text = shop.get("state", "")
                SubElement(shop_el, "ZipCode").text = shop.get("zip_code", "")
                SubElement(shop_el, "Phone").text = shop.get("phone", "")
                if shop.get("tax_id"):
                    SubElement(shop_el, "TaxID").text = shop["tax_id"]

            # Owner/Customer
            owner = SubElement(claim, "Owner")
            if est.get("company_name"):
                SubElement(owner, "CompanyName").text = est["company_name"]
            SubElement(owner, "FirstName").text = est.get("first_name", "")
            SubElement(owner, "LastName").text = est.get("last_name", "")
            SubElement(owner, "Address").text = est.get("address", "")
            SubElement(owner, "City").text = est.get("city", "")
            SubElement(owner, "State").text = est.get("state", "")
            SubElement(owner, "ZipCode").text = est.get("zip_code", "")
            SubElement(owner, "Phone").text = est.get("phone_home", "")
            SubElement(owner, "Email").text = est.get("email", "")

            # Vehicle
            veh = SubElement(claim, "Vehicle")
            SubElement(veh, "Year").text = str(est.get("year", ""))
            SubElement(veh, "Make").text = est.get("make", "")
            SubElement(veh, "Model").text = est.get("model", "")
            SubElement(veh, "Submodel").text = est.get("submodel", "")
            SubElement(veh, "VIN").text = est.get("vin", "")
            SubElement(veh, "Color").text = est.get("color", "")
            SubElement(veh, "LicensePlate").text = est.get("license_plate", "")
            SubElement(veh, "LicenseState").text = est.get("license_state", "")
            SubElement(veh, "Mileage").text = str(est.get("mileage", ""))
            if est.get("production_date"):
                SubElement(veh, "ProductionDate").text = est["production_date"]

            # Insurance
            if est.get("insurance_name"):
                ins = SubElement(claim, "InsuranceCompany")
                SubElement(ins, "CompanyName").text = est["insurance_name"]
                if est.get("insurance_phone"):
                    SubElement(ins, "Phone").text = est["insurance_phone"]

            # Line items
            lines_el = SubElement(claim, "LineItems")
            for line in est.get("lines", []):
                li = SubElement(lines_el, "LineItem")
                li.set("number", str(line.get("line_number", "")))
                SubElement(li, "LineType").text = line.get("line_type", "")
                SubElement(li, "Operation").text = line.get("operation", "")
                SubElement(li, "Description").text = line.get("description", "")
                if line.get("part_number"):
                    SubElement(li, "PartNumber").text = line["part_number"]
                if line.get("part_type"):
                    SubElement(li, "PartType").text = line["part_type"]
                SubElement(li, "Quantity").text = str(line.get("quantity", 1))
                SubElement(li, "LaborHours").text = str(line.get("labor_hours", 0))
                SubElement(li, "LaborRate").text = str(line.get("labor_rate", 0))
                SubElement(li, "PaintHours").text = str(line.get("paint_hours", 0))
                SubElement(li, "PaintRate").text = str(line.get("paint_rate", 0))
                SubElement(li, "PartPrice").text = str(line.get("part_price", 0))
                SubElement(li, "PartCost").text = str(line.get("part_cost", 0))
                SubElement(li, "LineTotal").text = str(line.get("line_total", 0))
                if line.get("is_supplement"):
                    SubElement(li, "IsSuplement").text = "true"
                    SubElement(li, "SupplementNumber").text = str(line.get("supplement_number", 0))

            # Totals
            totals = SubElement(claim, "Totals")
            SubElement(totals, "LaborTotal").text = str(est.get("subtotal_labor", 0))
            SubElement(totals, "PartsTotal").text = str(est.get("subtotal_parts", 0))
            SubElement(totals, "PaintTotal").text = str(est.get("subtotal_paint", 0))
            SubElement(totals, "OtherTotal").text = str(est.get("subtotal_other", 0))
            SubElement(totals, "TaxAmount").text = str(est.get("tax_amount", 0))
            SubElement(totals, "GrandTotal").text = str(est.get("total_amount", 0))

        raw = tostring(root, encoding="unicode")
        return parseString(raw).toprettyxml(indent="  ")
