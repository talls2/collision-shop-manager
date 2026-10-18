"""
Database schema definitions.
All CREATE TABLE and CREATE INDEX statements live here.
"""

TABLES = [
    # ── Body Shop Info ──
    """CREATE TABLE IF NOT EXISTS body_shop (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_name TEXT NOT NULL,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        phone TEXT,
        fax TEXT,
        email TEXT,
        tax_id TEXT,
        license_number TEXT,
        logo_path TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Customers ──
    """CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_type TEXT DEFAULT 'individual',
        first_name TEXT,
        last_name TEXT,
        company_name TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        billing_address TEXT,
        billing_city TEXT,
        billing_state TEXT,
        billing_zip TEXT,
        phone_home TEXT,
        phone_work TEXT,
        phone_cell TEXT,
        email TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Vehicles ──
    """CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER REFERENCES customers(id),
        vehicle_type TEXT DEFAULT 'tractor',
        vin TEXT,
        year INTEGER,
        make TEXT,
        model TEXT,
        submodel TEXT,
        color TEXT,
        license_plate TEXT,
        license_state TEXT,
        mileage INTEGER,
        engine_hours INTEGER,
        length_feet INTEGER,
        axle_count INTEGER,
        production_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Insurance Companies ──
    """CREATE TABLE IF NOT EXISTS insurance_companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        phone TEXT,
        fax TEXT,
        email TEXT,
        contact_name TEXT,
        policy_prefix TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Insurance Agents ──
    """CREATE TABLE IF NOT EXISTS insurance_agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        insurance_company_id INTEGER REFERENCES insurance_companies(id),
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        email TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Employees ──
    """CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_code TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        role TEXT DEFAULT 'technician'
            CHECK(role IN ('technician','estimator','manager','admin','painter','detailer','parts','office')),
        phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        hire_date TEXT,
        hourly_rate REAL DEFAULT 0,
        flag_rate REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Vendors ──
    """CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_name TEXT NOT NULL,
        contact_name TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        phone TEXT,
        fax TEXT,
        email TEXT,
        account_number TEXT,
        vendor_type TEXT DEFAULT 'parts',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Estimates ──
    """CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estimate_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER REFERENCES customers(id),
        vehicle_id INTEGER REFERENCES vehicles(id),
        insurance_company_id INTEGER REFERENCES insurance_companies(id),
        insurance_agent_id INTEGER REFERENCES insurance_agents(id),
        claim_number TEXT,
        policy_number TEXT,
        deductible REAL DEFAULT 0,
        estimator_id INTEGER REFERENCES employees(id),
        status TEXT DEFAULT 'draft'
            CHECK(status IN ('draft','pending','approved','rejected','converted')),
        loss_date TEXT,
        estimate_date TEXT DEFAULT (date('now')),
        sent_date TEXT,
        closed_date TEXT,
        point_of_impact TEXT,
        damage_description TEXT,
        subtotal_labor REAL DEFAULT 0,
        subtotal_parts REAL DEFAULT 0,
        subtotal_paint REAL DEFAULT 0,
        subtotal_other REAL DEFAULT 0,
        tax_amount REAL DEFAULT 0,
        tax_exempt INTEGER DEFAULT 0,
        total_amount REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Estimate Line Items ──
    """CREATE TABLE IF NOT EXISTS estimate_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
        line_number INTEGER NOT NULL,
        line_type TEXT NOT NULL CHECK(line_type IN ('labor','part','paint','sublet','other')),
        operation TEXT,
        description TEXT NOT NULL,
        part_number TEXT,
        part_type TEXT CHECK(part_type IN ('OEM','aftermarket','used','reconditioned','remanufactured')),
        quantity REAL DEFAULT 1,
        labor_hours REAL DEFAULT 0,
        labor_rate REAL DEFAULT 0,
        paint_hours REAL DEFAULT 0,
        paint_rate REAL DEFAULT 0,
        part_price REAL DEFAULT 0,
        part_cost REAL DEFAULT 0,
        line_total REAL DEFAULT 0,
        is_supplement INTEGER DEFAULT 0,
        supplement_number INTEGER DEFAULT 0,
        taxable INTEGER DEFAULT 1,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Repair Orders ──
    """CREATE TABLE IF NOT EXISTS repair_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ro_number TEXT UNIQUE NOT NULL,
        estimate_id INTEGER REFERENCES estimates(id),
        customer_id INTEGER REFERENCES customers(id),
        vehicle_id INTEGER REFERENCES vehicles(id),
        insurance_company_id INTEGER REFERENCES insurance_companies(id),
        insurance_agent_id INTEGER REFERENCES insurance_agents(id),
        claim_number TEXT,
        policy_number TEXT,
        deductible REAL DEFAULT 0,
        status TEXT DEFAULT 'open'
            CHECK(status IN ('open','in_progress','on_hold','completed','delivered','closed')),
        priority TEXT DEFAULT 'normal'
            CHECK(priority IN ('low','normal','high','rush')),
        loss_date TEXT,
        create_date TEXT DEFAULT (date('now')),
        estimate_sent_date TEXT,
        scheduled_in_date TEXT,
        vehicle_arrived_date TEXT,
        customer_signature_date TEXT,
        customer_signature TEXT,
        repair_start_date TEXT,
        internal_target_date TEXT,
        target_delivery_date TEXT,
        actual_complete_date TEXT,
        notify_customer_date TEXT,
        delivered_date TEXT,
        closed_date TEXT,
        estimator_id INTEGER REFERENCES employees(id),
        technician_id INTEGER REFERENCES employees(id),
        painter_id INTEGER REFERENCES employees(id),
        subtotal_labor REAL DEFAULT 0,
        subtotal_parts REAL DEFAULT 0,
        subtotal_paint REAL DEFAULT 0,
        subtotal_sublet REAL DEFAULT 0,
        subtotal_other REAL DEFAULT 0,
        tax_amount REAL DEFAULT 0,
        tax_exempt INTEGER DEFAULT 0,
        total_amount REAL DEFAULT 0,
        amount_paid REAL DEFAULT 0,
        balance_due REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── RO Line Items ──
    """CREATE TABLE IF NOT EXISTS ro_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ro_id INTEGER NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
        line_number INTEGER NOT NULL,
        line_type TEXT NOT NULL CHECK(line_type IN ('labor','part','paint','sublet','other')),
        operation TEXT,
        description TEXT NOT NULL,
        part_number TEXT,
        part_type TEXT CHECK(part_type IN ('OEM','aftermarket','used','reconditioned','remanufactured')),
        quantity REAL DEFAULT 1,
        labor_hours REAL DEFAULT 0,
        labor_rate REAL DEFAULT 0,
        paint_hours REAL DEFAULT 0,
        paint_rate REAL DEFAULT 0,
        part_price REAL DEFAULT 0,
        part_cost REAL DEFAULT 0,
        line_total REAL DEFAULT 0,
        is_supplement INTEGER DEFAULT 0,
        supplement_number INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending'
            CHECK(status IN ('pending','ordered','received','installed','complete')),
        assigned_tech_id INTEGER REFERENCES employees(id),
        vendor_id INTEGER REFERENCES vendors(id),
        taxable INTEGER DEFAULT 1,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── RO Team Assignments (many workers per RO, free-text role) ──
    """CREATE TABLE IF NOT EXISTS ro_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ro_id INTEGER NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        role TEXT NOT NULL,
        notes TEXT,
        assigned_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Payments ──
    """CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ro_id INTEGER NOT NULL REFERENCES repair_orders(id),
        payment_date TEXT DEFAULT (date('now')),
        amount REAL NOT NULL,
        payment_method TEXT CHECK(payment_method IN ('cash','check','credit_card','debit','insurance','other')),
        reference_number TEXT,
        payer_type TEXT CHECK(payer_type IN ('customer','insurance','other')),
        payer_name TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Part Invoices ──
    # ── Parts Catalog (price book that grows as parts are estimated) ──
    """CREATE TABLE IF NOT EXISTS parts_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT NOT NULL UNIQUE COLLATE NOCASE,
        description TEXT,
        standard_price REAL DEFAULT 0,
        standard_cost REAL DEFAULT 0,
        part_type TEXT,
        preferred_vendor_id INTEGER REFERENCES vendors(id),
        vehicle_compat TEXT,
        notes TEXT,
        usage_count INTEGER DEFAULT 0,
        last_used_date TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS part_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT,
        vendor_id INTEGER REFERENCES vendors(id),
        ro_id INTEGER REFERENCES repair_orders(id),
        invoice_date TEXT DEFAULT (date('now')),
        due_date TEXT,
        subtotal REAL DEFAULT 0,
        tax REAL DEFAULT 0,
        total REAL DEFAULT 0,
        is_credit_memo INTEGER DEFAULT 0,
        is_posted INTEGER DEFAULT 0,
        posted_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Part Invoice Lines ──
    """CREATE TABLE IF NOT EXISTS part_invoice_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL REFERENCES part_invoices(id) ON DELETE CASCADE,
        part_number TEXT,
        description TEXT,
        quantity REAL DEFAULT 1,
        unit_cost REAL DEFAULT 0,
        line_total REAL DEFAULT 0,
        ro_line_id INTEGER REFERENCES ro_lines(id),
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Time Cards ──
    """CREATE TABLE IF NOT EXISTS time_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        ro_id INTEGER REFERENCES repair_orders(id),
        clock_in TEXT NOT NULL,
        clock_out TEXT,
        hours_worked REAL DEFAULT 0,
        activity_type TEXT DEFAULT 'production'
            CHECK(activity_type IN ('production','non_production','break','meeting','training','cleanup','other')),
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Flag Pay ──
    """CREATE TABLE IF NOT EXISTS flag_pay (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        ro_id INTEGER REFERENCES repair_orders(id),
        ro_line_id INTEGER REFERENCES ro_lines(id),
        pay_period TEXT,
        hours_flagged REAL DEFAULT 0,
        rate REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        status TEXT DEFAULT 'open' CHECK(status IN ('open','paid')),
        paid_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Production Schedule ──
    """CREATE TABLE IF NOT EXISTS production_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ro_id INTEGER NOT NULL REFERENCES repair_orders(id),
        department TEXT CHECK(department IN ('body','frame','mechanical','paint','detail','assembly','glass','other')),
        scheduled_date TEXT,
        estimated_hours REAL DEFAULT 0,
        assigned_tech_id INTEGER REFERENCES employees(id),
        status TEXT DEFAULT 'scheduled'
            CHECK(status IN ('scheduled','in_progress','completed','on_hold')),
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Shop Rates ──
    """CREATE TABLE IF NOT EXISTS shop_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rate_name TEXT NOT NULL,
        rate_type TEXT,
        rate_amount REAL NOT NULL DEFAULT 0,
        effective_date TEXT DEFAULT (date('now')),
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Users (Auth) ──
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        pin_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'worker'
            CHECK(role IN ('admin','office','worker')),
        employee_id INTEGER REFERENCES employees(id),
        is_active INTEGER DEFAULT 1,
        last_login TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Sessions ──
    """CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        token TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    )""",

    # ── Vehicle Movements (TecStation tracking) ──
    """CREATE TABLE IF NOT EXISTS vehicle_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ro_id INTEGER NOT NULL REFERENCES repair_orders(id),
        from_department TEXT,
        to_department TEXT NOT NULL
            CHECK(to_department IN ('lot','body','frame','mechanical','paint','detail','assembly','glass','qa','ready','delivered')),
        moved_by INTEGER REFERENCES employees(id),
        moved_at TEXT DEFAULT (datetime('now')),
        notes TEXT
    )""",

    # ── Activity Log ──
    """CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        description TEXT,
        user_name TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",

    # ── Letter Templates ──
    """CREATE TABLE IF NOT EXISTS letter_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        template_type TEXT CHECK(template_type IN ('follow_up','work_authorization','customer_rights','thank_you','attorney','agent','custom')),
        subject TEXT,
        body_text TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles(vin)",
    "CREATE INDEX IF NOT EXISTS idx_estimates_customer ON estimates(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_estimates_vehicle ON estimates(vehicle_id)",
    "CREATE INDEX IF NOT EXISTS idx_estimates_status ON estimates(status)",
    "CREATE INDEX IF NOT EXISTS idx_ro_customer ON repair_orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_ro_vehicle ON repair_orders(vehicle_id)",
    "CREATE INDEX IF NOT EXISTS idx_ro_status ON repair_orders(status)",
    "CREATE INDEX IF NOT EXISTS idx_ro_number ON repair_orders(ro_number)",
    "CREATE INDEX IF NOT EXISTS idx_payments_ro ON payments(ro_id)",
    "CREATE INDEX IF NOT EXISTS idx_time_cards_employee ON time_cards(employee_id)",
    "CREATE INDEX IF NOT EXISTS idx_ro_assignments_ro ON ro_assignments(ro_id)",
    "CREATE INDEX IF NOT EXISTS idx_ro_assignments_employee ON ro_assignments(employee_id)",
    "CREATE INDEX IF NOT EXISTS idx_flag_pay_employee ON flag_pay(employee_id)",
    "CREATE INDEX IF NOT EXISTS idx_part_invoices_vendor ON part_invoices(vendor_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_log_entity ON activity_log(entity_type, entity_id)",
]
