"""
Seed data for shop_manager.

By default we seed the minimum required for a production-clean install:
  - Body shop record (placeholder — update via Admin → Settings)
  - Shop rates
  - Admin user (William, PIN 1234) + manager employee
  - Letter templates

Set env `SEED_DEMO=1` to ALSO insert demo customers, vehicles, insurance
companies, vendors, estimates, and sample ROs for development/testing.
"""
import hashlib
import os


def hash_pin(pin: str) -> str:
    """Simple PIN hashing. Replace with bcrypt for stronger security."""
    return hashlib.sha256(pin.encode()).hexdigest()


# ── Production essentials (always seeded on first run) ──────────────
def seed_production_data(conn):
    cur = conn.cursor()

    # ── Body Shop ──
    # Placeholder — owner should update via Admin → Settings on first login.
    cur.execute("""INSERT INTO body_shop (shop_name, address, city, state, zip_code, phone, email)
        VALUES ('Demo Collision & Truck Repair', '', '', 'MA', '', '(555) 010-0000', 'info@example.com')""")

    # ── Shop Rates ──
    for name, rtype, amt in [
        ('Body Labor',       'body_labor',       58.00),
        ('Paint Labor',      'paint_labor',      58.00),
        ('Mechanical Labor', 'mechanical_labor', 65.00),
        ('Frame Labor',      'frame_labor',      62.00),
        ('Glass Labor',      'glass_labor',      55.00),
        ('Paint Materials',  'paint_materials',  38.00),
        ('Sales Tax Rate %', 'sales_tax_rate',    6.25),  # MA state sales tax
    ]:
        cur.execute("INSERT INTO shop_rates (rate_name, rate_type, rate_amount) VALUES (?,?,?)",
                    (name, rtype, amt))

    # ── Manager employee (so admin user can reference an employee record) ──
    cur.execute("""INSERT INTO employees (employee_code, first_name, last_name, role, hourly_rate, flag_rate)
        VALUES ('E001', 'William', 'Benett', 'manager', 0, 0)""")

    # ── Admin user (change PIN on first login) ──
    cur.execute("""INSERT INTO users (username, pin_hash, display_name, role, employee_id)
        VALUES (?,?,?,?,?)""",
        ('admin', hash_pin('1234'), 'William (Admin)', 'admin', 1))

    # ── Letter Templates ──
    for name, ttype, subj, body in [
        ('Work Authorization', 'work_authorization', 'Vehicle Repair Authorization',
         'I hereby authorize {shop_name} to perform the repairs described in estimate {estimate_number} on my {vehicle_year} {vehicle_make} {vehicle_model}, VIN: {vin}.\n\nEstimated cost: ${total_amount}\nDeductible: ${deductible}\n\nSignature: _________________________\nDate: _________________________'),
        ('Thank You', 'thank_you', 'Thank You for Choosing {shop_name}',
         'Dear {customer_name},\n\nThank you for choosing {shop_name} for your vehicle repair. We appreciate your business.\n\nSincerely,\n{shop_name}'),
        ('Follow Up', 'follow_up', 'Follow-Up: Your Recent Repair',
         'Dear {customer_name},\n\nWe wanted to follow up on the recent repair of your {vehicle_year} {vehicle_make} {vehicle_model}. If you have any issues, please contact us at {shop_phone}.\n\nThank you,\n{shop_name}'),
    ]:
        cur.execute("INSERT INTO letter_templates (template_name, template_type, subject, body_text) VALUES (?,?,?,?)",
                    (name, ttype, subj, body))

    conn.commit()


# ── Demo data (off by default; enable with SEED_DEMO=1) ──────────────
def seed_demo_data(conn):
    cur = conn.cursor()

    # Extra demo employees
    for code, fn, ln, role, hr, fr in [
        ('E002', 'Carlos',  'Rivera',    'technician', 0,     28.00),
        ('E003', 'Mike',    'Johnson',   'painter',    0,     30.00),
        ('E004', 'Sarah',   'Williams',  'estimator',  35.00, 0),
        ('E005', 'David',   'Chen',      'technician', 0,     26.00),
        ('E006', 'Ana',     'Santos',    'detailer',   18.00, 0),
        ('E007', 'James',   'Brown',     'parts',      22.00, 0),
    ]:
        cur.execute("""INSERT INTO employees (employee_code, first_name, last_name, role, hourly_rate, flag_rate)
            VALUES (?,?,?,?,?,?)""", (code, fn, ln, role, hr, fr))

    # Demo worker user accounts
    for uname, pin, dname, eid in [
        ('office',  '5678', 'Sarah (Office)',  4),
        ('carlos',  '0001', 'Carlos Rivera',   2),
        ('mike',    '0002', 'Mike Johnson',    3),
        ('david',   '0003', 'David Chen',      5),
        ('ana',     '0004', 'Ana Santos',      6),
        ('james',   '0005', 'James Brown',     7),
    ]:
        role = 'office' if uname == 'office' else 'worker'
        cur.execute("""INSERT INTO users (username, pin_hash, display_name, role, employee_id)
            VALUES (?,?,?,?,?)""", (uname, hash_pin(pin), dname, role, eid))

    # Demo customers, vehicles, insurance companies, vendors, estimates, ROs
    for ct, fn, ln, cn, addr, city, st, zp, ph, em in [
        ('individual', 'John', 'Smith', None, '456 Oak Ave', 'Orlando', 'FL', '32801', '(407) 555-0201', 'john.smith@email.com'),
        ('individual', 'Maria', 'Garcia', None, '789 Pine St', 'Kissimmee', 'FL', '34741', '(407) 555-0302', 'maria.g@email.com'),
        ('company',     None,   None, 'ABC Fleet Services', '100 Commerce Dr', 'Orlando', 'FL', '32819', '(407) 555-0403', 'fleet@abcfleet.com'),
        ('individual', 'Robert', 'Taylor', None, '222 Elm Blvd', 'Winter Park', 'FL', '32789', '(407) 555-0504', 'rtaylor@email.com'),
        ('individual', 'Lisa', 'Martinez', None, '88 Maple Ct', 'Sanford', 'FL', '32771', '(407) 555-0605', 'lisa.m@email.com'),
    ]:
        cur.execute("""INSERT INTO customers (customer_type, first_name, last_name, company_name,
            address, city, state, zip_code, phone_home, email)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (ct, fn, ln, cn, addr, city, st, zp, ph, em))

    for cid, vin, yr, mk, md, sub, col, plate, pst, mi in [
        (1, '1HGBH41JXMN109186', 2021, 'Honda', 'Civic', 'EX', 'Lunar Silver', 'ABC1234', 'FL', 35200),
        (2, '5YJSA1DG9DFP14705', 2023, 'Tesla', 'Model S', 'Long Range', 'Pearl White', 'XYZ5678', 'FL', 12400),
        (3, '1FTEW1EP5MKE12345', 2022, 'Ford', 'F-150', 'XLT', 'Oxford White', 'FLT9012', 'FL', 48000),
        (4, '1G1YY22G965106789', 2020, 'Chevrolet', 'Corvette', 'Stingray', 'Torch Red', 'VET3456', 'FL', 22100),
        (5, '3MW5R1J05M8B12345', 2021, 'BMW', '330i', 'M Sport', 'Alpine White', 'BMW7890', 'FL', 29800),
    ]:
        cur.execute("""INSERT INTO vehicles (customer_id, vin, year, make, model, submodel, color,
            license_plate, license_state, mileage) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cid, vin, yr, mk, md, sub, col, plate, pst, mi))

    for name, addr, city, st, zp, ph in [
        ('State Farm',  '100 State Farm Blvd',   'Bloomington',      'IL', '61710', '(800) 782-8332'),
        ('GEICO',       '5260 Western Ave',      'Chevy Chase',      'MD', '20815', '(800) 841-3000'),
        ('Progressive', '6300 Wilson Mills Rd',  'Mayfield Village', 'OH', '44143', '(800) 776-4737'),
        ('Allstate',    '2775 Sanders Rd',       'Northbrook',       'IL', '60062', '(800) 255-7828'),
    ]:
        cur.execute("""INSERT INTO insurance_companies (company_name, address, city, state, zip_code, phone)
            VALUES (?,?,?,?,?,?)""", (name, addr, city, st, zp, ph))

    for name, contact, addr, city, st, zp, ph, vt in [
        ('LKQ Corporation', 'Parts Dept',     '501 Corporate Centre Dr', 'Franklin',   'TN', '37067', '(615) 771-5700', 'parts'),
        ('PPG Industries',  'Paint Dept',     '1 PPG Place',             'Pittsburgh', 'PA', '15222', '(412) 434-3131', 'paint'),
        ('AutoZone',        'Parts Counter',  '123 S Front St',          'Memphis',    'TN', '38103', '(800) 288-6966', 'parts'),
        ('3M Automotive',   'Materials',      '3M Center',               'St Paul',    'MN', '55144', '(888) 364-3577', 'materials'),
    ]:
        cur.execute("""INSERT INTO vendors (vendor_name, contact_name, address, city, state, zip_code, phone, vendor_type)
            VALUES (?,?,?,?,?,?,?,?)""", (name, contact, addr, city, st, zp, ph, vt))

    cur.execute("""INSERT INTO estimates (estimate_number, customer_id, vehicle_id, insurance_company_id,
        claim_number, deductible, estimator_id, status, loss_date, damage_description,
        subtotal_labor, subtotal_parts, subtotal_paint, tax_amount, total_amount)
        VALUES ('EST-2026-001', 1, 1, 1, 'CLM-8832901', 500.00, 4, 'approved', '2026-04-01',
        'Front-end collision. Hood, bumper cover, fender, headlamp assembly damaged.',
        1450.00, 2380.00, 680.00, 154.70, 4664.70)""")

    cur.execute("""INSERT INTO estimates (estimate_number, customer_id, vehicle_id, insurance_company_id,
        claim_number, deductible, estimator_id, status, loss_date, damage_description,
        subtotal_labor, subtotal_parts, subtotal_paint, tax_amount, total_amount)
        VALUES ('EST-2026-002', 2, 2, 2, 'CLM-7741002', 1000.00, 4, 'pending', '2026-04-10',
        'Rear quarter panel and bumper damage from parking lot incident.',
        980.00, 3200.00, 520.00, 208.00, 4908.00)""")

    cur.execute("""INSERT INTO estimates (estimate_number, customer_id, vehicle_id, insurance_company_id,
        claim_number, deductible, estimator_id, status, loss_date, damage_description,
        subtotal_labor, subtotal_parts, subtotal_paint, tax_amount, total_amount)
        VALUES ('EST-2026-003', 5, 5, 3, 'CLM-5529003', 500.00, 4, 'draft', '2026-04-12',
        'Side swipe damage to left doors and rocker panel.',
        1200.00, 1850.00, 750.00, 120.25, 3920.25)""")

    lines = [
        (1, 'labor', 'repair',   'R&I Front bumper cover',    None,             None,          1, 1.5, 58, 0, 0, 0,   0,   87.00),
        (2, 'part',  'replace',  'Hood Assembly',             'HON-60100-TBA',  'OEM',         1, 0,   0,  0, 0, 485, 380, 485.00),
        (3, 'labor', 'replace',  'Replace hood assembly',     None,             None,          1, 3.0, 58, 0, 0, 0,   0,   174.00),
        (4, 'part',  'replace',  'Front bumper cover',        'HON-04711-TBA',  'OEM',         1, 0,   0,  0, 0, 395, 290, 395.00),
        (5, 'part',  'replace',  'Left fender',               'HON-60261-TBA',  'aftermarket', 1, 0,   0,  0, 0, 220, 145, 220.00),
        (6, 'labor', 'replace',  'Replace left fender',       None,             None,          1, 3.5, 58, 0, 0, 0,   0,   203.00),
        (7, 'part',  'replace',  'Left headlamp assy',        'HON-33150-TBA',  'OEM',         1, 0,   0,  0, 0, 580, 420, 580.00),
        (8, 'labor', 'replace',  'Replace left headlamp',     None,             None,          1, 0.8, 58, 0, 0, 0,   0,   46.40),
        (9, 'paint', 'refinish', 'Refinish hood',             None,             None,          1, 0,   0,  3.5, 58, 0, 0, 203.00),
        (10,'paint', 'refinish', 'Refinish left fender',      None,             None,          1, 0,   0,  2.8, 58, 0, 0, 162.40),
        (11,'paint', 'blend',    'Blend right fender',        None,             None,          1, 0,   0,  2.0, 58, 0, 0, 116.00),
        (12,'part',  'replace',  'Hardware, clips, misc',     'MISC-001',       'OEM',         1, 0,   0,  0, 0, 120, 75,  120.00),
    ]
    for row in lines:
        cur.execute("""INSERT INTO estimate_lines (estimate_id, line_number, line_type, operation,
            description, part_number, part_type, quantity, labor_hours, labor_rate,
            paint_hours, paint_rate, part_price, part_cost, line_total)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)

    cur.execute("""INSERT INTO repair_orders (ro_number, estimate_id, customer_id, vehicle_id,
        insurance_company_id, claim_number, deductible, status, loss_date,
        scheduled_in_date, vehicle_arrived_date, repair_start_date, target_delivery_date,
        estimator_id, technician_id, painter_id,
        subtotal_labor, subtotal_parts, subtotal_paint, tax_amount, total_amount, balance_due)
        VALUES ('RO-2026-001', 1, 1, 1, 1, 'CLM-8832901', 500.00, 'in_progress',
        '2026-04-01', '2026-04-05', '2026-04-05', '2026-04-07', '2026-04-18',
        4, 2, 3, 1450.00, 2380.00, 680.00, 154.70, 4664.70, 4664.70)""")

    for row in lines:
        cur.execute("""INSERT INTO ro_lines (ro_id, line_number, line_type, operation,
            description, part_number, part_type, quantity, labor_hours, labor_rate,
            paint_hours, paint_rate, part_price, part_cost, line_total)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)

    cur.execute("UPDATE estimates SET status='converted' WHERE id=1")
    conn.commit()


# ── Public entry point (called from app.py startup) ──────────────────
def seed_initial_data(conn):
    """
    Seed the DB on first run. Always seeds production essentials.
    If SEED_DEMO=1, also seeds demo customers / vehicles / ROs.
    """
    cur = conn.cursor()
    if cur.execute("SELECT COUNT(*) FROM body_shop").fetchone()[0] > 0:
        return

    seed_production_data(conn)

    if os.environ.get("SEED_DEMO", "0") == "1":
        seed_demo_data(conn)
