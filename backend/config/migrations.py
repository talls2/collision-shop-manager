"""
Database migrations: idempotent schema upgrades that run on app startup.

Each migration checks whether it's needed before doing work, so it's safe
to re-run on every boot.
"""


def _has_legacy_operation_check(conn, table: str) -> bool:
    """Detect the old restrictive CHECK constraint on the operation column."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if not row or not row[0]:
        return False
    sql = row[0]
    return "operation IN ('repair','replace','refinish','blend','overhaul','sublet','other')" in sql


def _has_legacy_rate_type_check(conn) -> bool:
    """Detect the old restrictive CHECK constraint on shop_rates.rate_type."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='shop_rates'"
    ).fetchone()
    if not row or not row[0]:
        return False
    return "rate_type IN ('body_labor'" in row[0]


def _has_legacy_customer_type_check(conn) -> bool:
    """Detect the old restrictive CHECK on customers.customer_type."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='customers'"
    ).fetchone()
    if not row or not row[0]:
        return False
    return "customer_type IN ('individual','company')" in row[0]


def _drop_customer_type_check(conn) -> None:
    """Rebuild customers without the restrictive customer_type CHECK."""
    cur = conn.cursor()
    cols_info = cur.execute("PRAGMA table_info(customers)").fetchall()
    src_col_names = [c[1] for c in cols_info]

    cur.execute("PRAGMA foreign_keys = OFF")
    try:
        cur.execute("""
            CREATE TABLE customers__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_type TEXT DEFAULT 'individual',
                first_name TEXT,
                last_name TEXT,
                company_name TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip_code TEXT,
                phone_home TEXT,
                phone_work TEXT,
                phone_cell TEXT,
                email TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Only copy columns that exist on BOTH the old and the new table.
        new_col_names = {c[1] for c in cur.execute("PRAGMA table_info(customers__new)").fetchall()}
        copy_cols = [c for c in src_col_names if c in new_col_names]
        copy_list = ", ".join(copy_cols)
        cur.execute(f"INSERT INTO customers__new ({copy_list}) SELECT {copy_list} FROM customers")
        cur.execute("DROP TABLE customers")
        cur.execute("ALTER TABLE customers__new RENAME TO customers")
        conn.commit()
    finally:
        cur.execute("PRAGMA foreign_keys = ON")


def _has_legacy_vendor_type_check(conn) -> bool:
    """Detect the old restrictive CHECK constraint on vendors.vendor_type."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vendors'"
    ).fetchone()
    if not row or not row[0]:
        return False
    return "vendor_type IN ('parts'" in row[0]


def _drop_vendor_type_check(conn) -> None:
    """Rebuild vendors without the restrictive vendor_type CHECK."""
    cur = conn.cursor()
    cols_info = cur.execute("PRAGMA table_info(vendors)").fetchall()
    col_names = [c[1] for c in cols_info]

    cur.execute("PRAGMA foreign_keys = OFF")
    try:
        cur.execute("""
            CREATE TABLE vendors__new (
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
            )
        """)
        new_cols_info = cur.execute("PRAGMA table_info(vendors__new)").fetchall()
        new_col_names = {c[1] for c in new_cols_info}
        copy_cols = [c for c in col_names if c in new_col_names]
        copy_list = ", ".join(copy_cols)
        cur.execute(f"INSERT INTO vendors__new ({copy_list}) SELECT {copy_list} FROM vendors")
        cur.execute("DROP TABLE vendors")
        cur.execute("ALTER TABLE vendors__new RENAME TO vendors")
        conn.commit()
    finally:
        cur.execute("PRAGMA foreign_keys = ON")


def _drop_shop_rates_check(conn) -> None:
    """Rebuild shop_rates without the restrictive rate_type CHECK."""
    cur = conn.cursor()
    cols_info = cur.execute("PRAGMA table_info(shop_rates)").fetchall()
    col_names = [c[1] for c in cols_info]
    col_list = ", ".join(col_names)

    cur.execute("PRAGMA foreign_keys = OFF")
    try:
        cur.execute("""
            CREATE TABLE shop_rates__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rate_name TEXT NOT NULL,
                rate_type TEXT,
                rate_amount REAL NOT NULL DEFAULT 0,
                effective_date TEXT DEFAULT (date('now')),
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        new_cols_info = cur.execute("PRAGMA table_info(shop_rates__new)").fetchall()
        new_col_names = {c[1] for c in new_cols_info}
        copy_cols = [c for c in col_names if c in new_col_names]
        copy_list = ", ".join(copy_cols)
        cur.execute(f"INSERT INTO shop_rates__new ({copy_list}) SELECT {copy_list} FROM shop_rates")
        cur.execute("DROP TABLE shop_rates")
        cur.execute("ALTER TABLE shop_rates__new RENAME TO shop_rates")
        conn.commit()
    finally:
        cur.execute("PRAGMA foreign_keys = ON")


def _drop_operation_check(conn, table: str, fk_parent_col: str) -> None:
    """
    Recreate `table` without the restrictive CHECK on `operation`.
    SQLite can't ALTER constraints, so we rebuild: rename → create new → copy → drop.
    `fk_parent_col` is the FK column name (estimate_id or ro_id).
    """
    cur = conn.cursor()

    # Get the column list from the existing table (preserves any future-added columns).
    cols_info = cur.execute(f"PRAGMA table_info({table})").fetchall()
    col_names = [c[1] for c in cols_info]
    col_list = ", ".join(col_names)

    parent_table = "estimates" if fk_parent_col == "estimate_id" else "repair_orders"
    extra_status = ""
    if table == "ro_lines":
        extra_status = (
            "status TEXT DEFAULT 'pending' "
            "CHECK(status IN ('pending','ordered','received','installed','complete')), "
            "assigned_tech_id INTEGER REFERENCES employees(id), "
            "vendor_id INTEGER REFERENCES vendors(id), "
        )

    new_sql = f"""
    CREATE TABLE {table}__new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {fk_parent_col} INTEGER NOT NULL REFERENCES {parent_table}(id) ON DELETE CASCADE,
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
        {extra_status}
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """

    # Run inside a transaction; FKs OFF temporarily so the rebuild doesn't trip.
    cur.execute("PRAGMA foreign_keys = OFF")
    try:
        cur.execute(new_sql)

        # Build the column intersection so we don't break if either table has extra columns.
        new_cols_info = cur.execute(f"PRAGMA table_info({table}__new)").fetchall()
        new_col_names = {c[1] for c in new_cols_info}
        copy_cols = [c for c in col_names if c in new_col_names]
        copy_list = ", ".join(copy_cols)

        cur.execute(f"INSERT INTO {table}__new ({copy_list}) SELECT {copy_list} FROM {table}")
        cur.execute(f"DROP TABLE {table}")
        cur.execute(f"ALTER TABLE {table}__new RENAME TO {table}")
        conn.commit()
    finally:
        cur.execute("PRAGMA foreign_keys = ON")


def _has_column(conn, table: str, column: str) -> bool:
    """Return True if `table` already has `column`."""
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c[1] == column for c in cols)


def _add_column(conn, table: str, column: str, ddl: str) -> None:
    """Idempotent ALTER TABLE ADD COLUMN."""
    if not _has_column(conn, table, column):
        print(f"[migration] Adding {table}.{column}")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.commit()


def run_migrations(conn) -> None:
    """Run all pending migrations. Safe to call on every startup."""
    # Migration 001: drop restrictive operation CHECK on estimate_lines / ro_lines.
    if _has_legacy_operation_check(conn, "estimate_lines"):
        print("[migration] Removing restrictive operation CHECK on estimate_lines")
        _drop_operation_check(conn, "estimate_lines", "estimate_id")

    if _has_legacy_operation_check(conn, "ro_lines"):
        print("[migration] Removing restrictive operation CHECK on ro_lines")
        _drop_operation_check(conn, "ro_lines", "ro_id")

    # Migration 002: tax_exempt on documents + taxable on lines.
    _add_column(conn, "estimates",      "tax_exempt", "INTEGER DEFAULT 0")
    _add_column(conn, "repair_orders",  "tax_exempt", "INTEGER DEFAULT 0")

    # Migration 002b: time_cards.updated_at — base repo touches updated_at on
    # every UPDATE, so missing this column made clock-out fail silently with
    # "no such column: updated_at".
    _add_column(conn, "time_cards", "updated_at", "TEXT")

    # Migration 002d: parts_catalog (price book for re-use across estimates).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parts_catalog (
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
        )
    """)
    conn.commit()

    # Migration 002c: vehicle type + type-specific fields. Existing rows default
    # to 'tractor' (most common at this shop) so the UI keeps showing VIN and
    # mileage by default; admin can change the type per vehicle.
    _add_column(conn, "vehicles", "vehicle_type",  "TEXT DEFAULT 'tractor'")
    _add_column(conn, "vehicles", "engine_hours",  "INTEGER")
    _add_column(conn, "vehicles", "length_feet",   "INTEGER")
    _add_column(conn, "vehicles", "axle_count",    "INTEGER")
    # Backfill any nulls from earlier ALTER (SQLite ALTER ADD COLUMN with
    # DEFAULT only applies to new rows in some Python versions).
    conn.execute("UPDATE vehicles SET vehicle_type = 'tractor' WHERE vehicle_type IS NULL")
    conn.commit()

    # For lines: default new column to 1, but for EXISTING rows we want only
    # parts taxable (preserves the previous parts-only tax behavior).
    for table in ("estimate_lines", "ro_lines"):
        if not _has_column(conn, table, "taxable"):
            print(f"[migration] Adding {table}.taxable and back-filling")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN taxable INTEGER DEFAULT 1")
            conn.execute(f"UPDATE {table} SET taxable = CASE WHEN line_type = 'part' THEN 1 ELSE 0 END")
            conn.commit()

    # Migration 003: drop restrictive shop_rates.rate_type CHECK so we can add
    # arbitrary rate types (e.g. sales_tax_rate) without hitting the old enum.
    if _has_legacy_rate_type_check(conn):
        print("[migration] Removing restrictive rate_type CHECK on shop_rates")
        _drop_shop_rates_check(conn)

    # Migration 003b: drop restrictive vendors.vendor_type CHECK so the user
    # can type any role (e.g. "accountant") instead of picking from 5 fixed values.
    if _has_legacy_vendor_type_check(conn):
        print("[migration] Removing restrictive vendor_type CHECK on vendors")
        _drop_vendor_type_check(conn)

    # Migration 003d: drop restrictive customers.customer_type CHECK.
    if _has_legacy_customer_type_check(conn):
        print("[migration] Removing restrictive customer_type CHECK on customers")
        _drop_customer_type_check(conn)

    # Migration 003e: billing address fields on customers. Often the truck's
    # physical address ("ship to") differs from where invoices get mailed
    # ("bill to") — especially for fleets with a separate accounting office.
    _add_column(conn, "customers", "billing_address", "TEXT")
    _add_column(conn, "customers", "billing_city",    "TEXT")
    _add_column(conn, "customers", "billing_state",   "TEXT")
    _add_column(conn, "customers", "billing_zip",     "TEXT")

    # Migration 003f: customer signature capture on ROs. Stores a base64-encoded
    # PNG of the customer's signature for work authorization.
    _add_column(conn, "repair_orders", "customer_signature", "TEXT")

    # Migration 003g: estimates.closed_date — stamped when an estimate moves to
    # a terminal status (converted / rejected / approved).
    _add_column(conn, "estimates", "closed_date", "TEXT")
    # Backfill for existing rows in terminal states: use updated_at as best
    # available proxy for "when did this stop being active".
    conn.execute("""
        UPDATE estimates
           SET closed_date = COALESCE(closed_date, DATE(updated_at), DATE(created_at))
         WHERE status IN ('converted','rejected','approved')
           AND closed_date IS NULL
    """)
    conn.commit()

    # Migration 003c: ro_assignments join table for multi-worker assignment.
    # CREATE IF NOT EXISTS already handles fresh installs via TABLES, but on
    # a live DB we also back-fill from the legacy fixed columns the first time.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ro_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ro_id INTEGER NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            role TEXT NOT NULL,
            notes TEXT,
            assigned_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ro_assignments_ro ON ro_assignments(ro_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ro_assignments_employee ON ro_assignments(employee_id)")
    conn.commit()

    # Back-fill assignments from legacy fixed columns — only if the table is empty.
    has_any = conn.execute("SELECT COUNT(*) FROM ro_assignments").fetchone()[0]
    if not has_any:
        for col, role in (("estimator_id","estimator"), ("technician_id","technician"), ("painter_id","painter")):
            try:
                rows = conn.execute(
                    f"SELECT id, {col} FROM repair_orders WHERE {col} IS NOT NULL"
                ).fetchall()
            except Exception:
                rows = []
            for ro_id, emp_id in rows:
                conn.execute(
                    "INSERT INTO ro_assignments (ro_id, employee_id, role) VALUES (?, ?, ?)",
                    (ro_id, emp_id, role),
                )
        conn.commit()
        if any(True for _ in conn.execute("SELECT 1 FROM ro_assignments LIMIT 1")):
            print("[migration] Back-filled ro_assignments from legacy estimator/technician/painter columns")

    # Migration 004: add configurable sales_tax_rate to shop_rates if missing.
    row = conn.execute(
        "SELECT id FROM shop_rates WHERE rate_type = 'sales_tax_rate'"
    ).fetchone()
    if not row:
        print("[migration] Seeding default sales_tax_rate (6.25%)")
        conn.execute(
            "INSERT INTO shop_rates (rate_name, rate_type, rate_amount) VALUES (?,?,?)",
            ("Sales Tax Rate %", "sales_tax_rate", 6.25),
        )
        conn.commit()
