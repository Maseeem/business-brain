import json
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime
from pathlib import Path

DB_PATH = Path("business_brain.db")

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def _ensure_columns(c, table, columns):
    existing = {row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

def init_db():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, profile TEXT DEFAULT '', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS processes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1, name TEXT NOT NULL DEFAULT 'Untitled Process',
        description TEXT DEFAULT '', category TEXT DEFAULT 'Operations', owner TEXT DEFAULT 'Business Owner', status TEXT DEFAULT 'Active',
        trigger TEXT DEFAULT '', inputs_json TEXT DEFAULT '[]', roles_json TEXT DEFAULT '[]', steps_json TEXT DEFAULT '[]',
        decisions_json TEXT DEFAULT '[]', exceptions_json TEXT DEFAULT '[]', output TEXT DEFAULT '', tags_json TEXT DEFAULT '[]',
        created_at TEXT DEFAULT '', updated_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1, title TEXT NOT NULL DEFAULT 'Untitled knowledge',
        type TEXT DEFAULT 'Document', description TEXT DEFAULT '', source TEXT DEFAULT '', status TEXT DEFAULT 'Indexed',
        tags_json TEXT DEFAULT '[]', content TEXT DEFAULT '', created_at TEXT DEFAULT '', updated_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1, source_type TEXT NOT NULL DEFAULT 'knowledge',
        source_id INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL DEFAULT 'Untitled source', content TEXT NOT NULL DEFAULT '',
        metadata_json TEXT DEFAULT '{}', created_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS process_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, process_id INTEGER NOT NULL, version INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL, changed_by_user_id INTEGER DEFAULT 0, changed_by TEXT DEFAULT 'System',
        change_note TEXT DEFAULT '', created_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'Employee',
        status TEXT DEFAULT 'Active', created_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1, action TEXT NOT NULL DEFAULT '',
        details TEXT DEFAULT '', created_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL, aliases TEXT DEFAULT '', price REAL, stock_quantity REAL NOT NULL DEFAULT 0,
        minimum_stock REAL NOT NULL DEFAULT 0, unit TEXT DEFAULT 'unit', active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
        UNIQUE(business_id, name)
    );
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL, contact TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
        UNIQUE(business_id, name)
    );
    CREATE TABLE IF NOT EXISTS supplier_products (
        supplier_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        supplier_product_name TEXT DEFAULT '', supplier_price REAL,
        PRIMARY KEY (supplier_id, product_id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1,
        transaction_ref TEXT NOT NULL UNIQUE, total REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Confirmed', created_by INTEGER DEFAULT 0, created_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        quantity REAL NOT NULL, unit_price REAL NOT NULL, subtotal REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS supplier_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1,
        supplier_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Draft',
        created_by INTEGER DEFAULT 0, approved_by INTEGER DEFAULT 0,
        created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
    );
    CREATE TABLE IF NOT EXISTS supplier_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        quantity REAL NOT NULL, unit_price REAL,
        FOREIGN KEY (supplier_order_id) REFERENCES supplier_orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS receipt_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1, sale_id INTEGER,
        status TEXT NOT NULL DEFAULT 'Needs Review', extracted_receipt_json TEXT DEFAULT '{}',
        mismatches_json TEXT DEFAULT '[]', created_by INTEGER DEFAULT 0, created_at TEXT DEFAULT '',
        FOREIGN KEY (sale_id) REFERENCES sales(id)
    );
    CREATE TABLE IF NOT EXISTS business_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL DEFAULT 1,
        memory_type TEXT NOT NULL DEFAULT 'fact', key TEXT NOT NULL, value TEXT NOT NULL,
        source TEXT DEFAULT 'owner', confidence REAL DEFAULT 1.0, created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
        UNIQUE(business_id, memory_type, key)
    );
    """)

    # Migrate older MVP databases created before the final schema.
    _ensure_columns(c, "processes", {
        "business_id": "INTEGER NOT NULL DEFAULT 1", "description": "TEXT DEFAULT ''", "category": "TEXT DEFAULT 'Operations'",
        "owner": "TEXT DEFAULT 'Business Owner'", "status": "TEXT DEFAULT 'Active'", "trigger": "TEXT DEFAULT ''",
        "inputs_json": "TEXT DEFAULT '[]'", "roles_json": "TEXT DEFAULT '[]'", "steps_json": "TEXT DEFAULT '[]'",
        "decisions_json": "TEXT DEFAULT '[]'", "exceptions_json": "TEXT DEFAULT '[]'", "output": "TEXT DEFAULT ''",
        "tags_json": "TEXT DEFAULT '[]'", "created_at": "TEXT DEFAULT ''", "updated_at": "TEXT DEFAULT ''"})
    _ensure_columns(c, "knowledge", {
        "business_id": "INTEGER NOT NULL DEFAULT 1", "type": "TEXT DEFAULT 'Document'", "description": "TEXT DEFAULT ''",
        "source": "TEXT DEFAULT ''", "status": "TEXT DEFAULT 'Indexed'", "tags_json": "TEXT DEFAULT '[]'",
        "content": "TEXT DEFAULT ''", "created_at": "TEXT DEFAULT ''", "updated_at": "TEXT DEFAULT ''"})
    _ensure_columns(c, "chunks", {
        "business_id": "INTEGER NOT NULL DEFAULT 1", "source_type": "TEXT NOT NULL DEFAULT 'knowledge'",
        "source_id": "INTEGER NOT NULL DEFAULT 0", "title": "TEXT NOT NULL DEFAULT 'Untitled source'",
        "content": "TEXT NOT NULL DEFAULT ''", "metadata_json": "TEXT DEFAULT '{}'", "created_at": "TEXT DEFAULT ''"})
    _ensure_columns(c, "process_versions", {
        "process_id": "INTEGER NOT NULL DEFAULT 0", "version": "INTEGER NOT NULL DEFAULT 1",
        "snapshot_json": "TEXT NOT NULL DEFAULT '{}'", "changed_by_user_id": "INTEGER DEFAULT 0",
        "changed_by": "TEXT DEFAULT 'System'", "change_note": "TEXT DEFAULT ''", "created_at": "TEXT DEFAULT ''"})
    _ensure_columns(c, "users", {
        "business_id": "INTEGER NOT NULL DEFAULT 1", "name": "TEXT DEFAULT 'User'",
        "username": "TEXT DEFAULT ''", "password_hash": "TEXT DEFAULT ''", "role": "TEXT DEFAULT 'Employee'",
        "status": "TEXT DEFAULT 'Active'", "created_at": "TEXT DEFAULT ''"})
    _ensure_columns(c, "activity", {
        "business_id": "INTEGER NOT NULL DEFAULT 1", "action": "TEXT NOT NULL DEFAULT ''",
        "details": "TEXT DEFAULT ''", "created_at": "TEXT DEFAULT ''"})

    # Backfill version 1 for processes created by older MVP databases.
    rows = c.execute("SELECT id,name,description,category,owner,status,trigger,inputs_json,roles_json,steps_json,decisions_json,exceptions_json,output,tags_json FROM processes WHERE business_id=1").fetchall()
    for r in rows:
        exists = c.execute("SELECT 1 FROM process_versions WHERE process_id=? LIMIT 1", (r[0],)).fetchone()
        if not exists:
            snapshot = {"name":r[1],"description":r[2],"category":r[3],"owner":r[4],"status":r[5],"trigger":r[6],"inputs":json.loads(r[7] or "[]"),"roles":json.loads(r[8] or "[]"),"steps":json.loads(r[9] or "[]"),"decisions":json.loads(r[10] or "[]"),"exceptions":json.loads(r[11] or "[]"),"output":r[12],"tags":json.loads(r[13] or "[]")}
            c.execute("INSERT INTO process_versions (process_id,version,snapshot_json,changed_by_user_id,changed_by,change_note,created_at) VALUES (?,?,?,?,?,?,?)", (r[0],1,json.dumps(snapshot),0,"System","Backfilled from existing process",datetime.now().isoformat(timespec="seconds")))

    c.commit()
    c.close()

def seed_demo_data():
    c = _conn()
    existing = c.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    if existing:
        c.close()
        seed_operational_data()
        return

    now = datetime.now().isoformat(timespec="seconds")
    c.execute(
        "INSERT OR IGNORE INTO businesses (id,name,profile,created_at) VALUES (1,?,?,?)",
        ("Nova Bakery", "A neighborhood bakery specializing in fresh bread, celebration cakes, and custom orders.", now)
    )

    demo_processes = [
        {
            "name": "New Customer Order",
            "description": "Standard workflow for receiving, validating and routing customer orders.",
            "category": "Sales",
            "trigger": "A customer submits an order by phone, message, walk-in, or approved order channel.",
            "inputs": ["Customer name and contact", "Items requested", "Quantity", "Requested date/time", "Delivery or pickup details", "Payment details when required"],
            "roles": ["Front counter / sales", "Production team"],
            "steps": [
                {"action": "Receive the customer order"},
                {"action": "Verify required customer and order information"},
                {"action": "Check product availability and requested timing"},
                {"action": "Confirm price, pickup/delivery details and any special requirements"},
                {"action": "Send the customer a confirmation"},
                {"action": "Create or update the order record"},
                {"action": "Forward production details to the relevant team"},
                {"action": "Update order status as it progresses"},
            ],
            "decisions": ["If requested items are unavailable, offer an approved alternative or another date.", "If a custom request is outside standard offerings, escalate to the bakery lead."],
            "exceptions": ["Do not promise a delivery time until availability and capacity are confirmed.", "Flag allergy-related questions for human review."],
            "output": "A confirmed order with complete details and a clear owner.",
            "tags": ["orders", "sales", "customer-service"],
        },
        {
            "name": "Custom Cake Order",
            "description": "Workflow for handling custom celebration cake requests.",
            "category": "Production",
            "trigger": "Customer requests a cake that requires customization.",
            "inputs": ["Cake size", "Flavor", "Design/theme", "Pickup date", "Reference image if applicable", "Customer contact"],
            "roles": ["Customer service", "Cake decorator", "Production lead"],
            "steps": [
                {"action": "Capture the cake requirements and reference material"},
                {"action": "Confirm whether the requested design is feasible"},
                {"action": "Calculate or confirm the approved price"},
                {"action": "Confirm the pickup date and payment requirement"},
                {"action": "Record the approved design and specifications"},
                {"action": "Assign the work to the cake decorator"},
                {"action": "Complete quality check before handoff"},
            ],
            "decisions": ["If design feasibility is uncertain, ask the cake decorator before confirming.", "If the requested date is full, offer the next available date."],
            "exceptions": ["Never confirm a custom design before feasibility is checked."],
            "output": "A confirmed custom cake order with documented specifications.",
            "tags": ["cakes", "custom-orders", "production"],
        },
        {
            "name": "Inventory Restocking",
            "description": "Routine process for checking stock and replenishing essential ingredients and packaging.",
            "category": "Operations",
            "trigger": "Scheduled inventory check or a low-stock alert.",
            "inputs": ["Current stock levels", "Minimum stock levels", "Supplier list", "Upcoming production needs"],
            "roles": ["Inventory owner", "Bakery manager"],
            "steps": [
                {"action": "Review current stock against minimum levels"},
                {"action": "Identify ingredients or packaging that need replenishment"},
                {"action": "Check upcoming production needs"},
                {"action": "Prepare the supplier order"},
                {"action": "Confirm quantities and delivery expectations"},
                {"action": "Update the inventory record when goods arrive"},
            ],
            "decisions": ["Prioritize critical ingredients required for confirmed customer orders."],
            "exceptions": ["Escalate supplier delays that could affect confirmed orders."],
            "output": "Restocked inventory with updated records.",
            "tags": ["inventory", "suppliers"],
        },
        {
            "name": "Customer Complaint Handling",
            "description": "Structured approach for acknowledging, investigating and resolving customer complaints.",
            "category": "Customer Service",
            "trigger": "A customer reports a problem with a product or service.",
            "inputs": ["Customer details", "Order details", "Description of issue", "Relevant evidence"],
            "roles": ["Customer service", "Bakery manager"],
            "steps": [
                {"action": "Listen and record the complaint accurately"},
                {"action": "Locate the relevant order"},
                {"action": "Review the facts and evidence"},
                {"action": "Escalate when manager review is required"},
                {"action": "Offer an approved resolution"},
                {"action": "Record the outcome and any follow-up needed"},
            ],
            "decisions": ["Refund or replacement decisions must follow the Refund Policy."],
            "exceptions": ["Do not promise a refund before checking the applicable policy."],
            "output": "A documented complaint outcome and follow-up action when needed.",
            "tags": ["complaints", "customer-service"],
        },
    ]

    for p in demo_processes:
        _insert_process(c, p, now)
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        _save_version(c, pid, p, 0, "System", "Demo process")

    demo_knowledge = [
        ("Customer Service Policy", "Policy", "Guidelines for professional customer communication and escalation.", "Customer Service Policy", ["customer-service", "policy"],
         "Customer concerns should be acknowledged respectfully and recorded accurately. Escalate complaints that require manager review. Do not promise refunds or replacements before checking the applicable refund policy."),
        ("Pricing Guide", "Guide", "Reference for standard product and custom order pricing.", "Pricing Guide", ["pricing", "sales"],
         "Standard products use the current approved price list. Custom cake prices depend on size, flavor, design complexity and approved customization. If a requested design is unusual, confirm feasibility before confirming the final price."),
        ("Order Requirements", "Guide", "Information that should be collected before an order is confirmed.", "Order Requirements", ["orders", "sales"],
         "Before confirming a customer order, collect customer name and contact details, requested items and quantities, requested date or time, pickup or delivery details, and payment information when required. Custom orders should also include specifications and reference material when relevant."),
        ("Refund Policy", "Policy", "Rules for handling refund and replacement requests.", "Refund Policy", ["refunds", "policy"],
         "Refund or replacement decisions require review against the applicable order circumstances. Staff should not promise a refund before checking the policy and escalating to the bakery manager when needed."),
    ]
    for title, kind, desc, source, tags, content in demo_knowledge:
        c.execute("""INSERT INTO knowledge
        (business_id,title,type,description,source,status,tags_json,content,created_at,updated_at)
        VALUES (1,?,?,?,?,?,?,?,?,?)""",
                  (title, kind, desc, source, "Indexed", json.dumps(tags), content, now, now))

    # Demo users for the MVP. Replace/change these credentials before production use.
    demo_users = [
        ("Business Owner", "admin", "BusinessBrain123!", "Owner"),
        ("Bakery Manager", "manager", "BusinessBrain123!", "Manager"),
        ("Team Employee", "employee", "BusinessBrain123!", "Employee"),
    ]
    for uname_name, username, password, role in demo_users:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
        stored = f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"
        c.execute("INSERT OR IGNORE INTO users (business_id,name,username,password_hash,role,status,created_at) VALUES (1,?,?,?,?,?,?)",
                  (uname_name, username, stored, role, "Active", now))

    c.commit()
    c.close()
    seed_operational_data()

def ensure_demo_users():
    """Ensure the MVP demo accounts exist after migrating an older database."""
    c=_conn()
    now=datetime.now().isoformat(timespec="seconds")
    demo_users=[("Business Owner","admin","BusinessBrain123!","Owner"),("Bakery Manager","manager","BusinessBrain123!","Manager"),("Team Employee","employee","BusinessBrain123!","Employee")]
    for uname_name,username,password,role in demo_users:
        exists=c.execute("SELECT 1 FROM users WHERE username=?",(username,)).fetchone()
        if not exists:
            salt=secrets.token_bytes(16); digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,200000)
            stored=f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"
            c.execute("INSERT INTO users (business_id,name,username,password_hash,role,status,created_at) VALUES (1,?,?,?,?,?,?)",(uname_name,username,stored,role,"Active",now))
    c.commit(); c.close()

def _insert_process(c, p, now):
    c.execute("""INSERT INTO processes
    (business_id,name,description,category,owner,status,trigger,inputs_json,roles_json,steps_json,decisions_json,exceptions_json,output,tags_json,created_at,updated_at)
    VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (p["name"], p["description"], p["category"], "Business Owner", "Active", p["trigger"],
     json.dumps(p["inputs"]), json.dumps(p["roles"]), json.dumps(p["steps"]),
     json.dumps(p["decisions"]), json.dumps(p["exceptions"]), p["output"], json.dumps(p["tags"]), now, now))

def get_business():
    c = _conn()
    row = c.execute("SELECT * FROM businesses WHERE id=1").fetchone()
    c.close()
    return dict(row)

def _verify_password(stored, password):
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256": return False
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(calculated, digest_hex)
    except Exception:
        return False

def authenticate_user(username, password):
    c = _conn()
    row = c.execute("SELECT * FROM users WHERE username=? AND business_id=1 AND status='Active'", ((username or "").strip().lower(),)).fetchone()
    c.close()
    if not row or not _verify_password(row["password_hash"], password):
        return None
    d=dict(row); d.pop("password_hash", None); return d

def list_users():
    c=_conn(); rows=c.execute("SELECT id,name,username,role,status,created_at FROM users WHERE business_id=1 ORDER BY id").fetchall(); c.close(); return [dict(r) for r in rows]

def _hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"

def create_user(name, username, password, role):
    name = (name or "").strip()
    username = (username or "").strip().lower()
    password = password or ""
    role = role if role in {"Owner", "Manager", "Employee"} else "Employee"
    if not name or not username or not password:
        raise ValueError("Name, username and password are required.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    try:
        c.execute("INSERT INTO users (business_id,name,username,password_hash,role,status,created_at) VALUES (1,?,?,?,?,?,?)",
                  (name, username, _hash_password(password), role, "Active", now))
        uid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.commit()
        return uid
    finally:
        c.close()

def get_user(user_id):
    c = _conn()
    row = c.execute("SELECT id,name,username,role,status,created_at FROM users WHERE id=? AND business_id=1", (user_id,)).fetchone()
    c.close()
    return dict(row) if row else None

def update_user(user_id, name=None, role=None, status=None):
    if not user_id:
        return False
    allowed_roles = {"Owner", "Manager", "Employee"}
    allowed_status = {"Active", "Inactive"}
    c = _conn()
    row = c.execute("SELECT * FROM users WHERE id=? AND business_id=1", (user_id,)).fetchone()
    if not row:
        c.close(); return False
    new_name = (name if name is not None else row["name"]).strip()
    new_role = role if role in allowed_roles else row["role"]
    new_status = status if status in allowed_status else row["status"]
    if not new_name:
        c.close(); raise ValueError("Name cannot be empty.")
    # Never allow the workspace to lose its final active Owner.
    if (row["role"] == "Owner" and row["status"] == "Active" and
        (new_role != "Owner" or new_status != "Active")):
        owners = c.execute("SELECT COUNT(*) FROM users WHERE business_id=1 AND role='Owner' AND status='Active'").fetchone()[0]
        if owners <= 1:
            c.close(); raise ValueError("The last active Owner cannot be deactivated or changed to another role.")
    c.execute("UPDATE users SET name=?, role=?, status=? WHERE id=? AND business_id=1",
              (new_name, new_role, new_status, user_id))
    changed = c.execute("SELECT changes()").fetchone()[0] > 0
    c.commit(); c.close()
    return changed

def reset_user_password(user_id, new_password):
    new_password = new_password or ""
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    c = _conn()
    cur = c.execute("UPDATE users SET password_hash=? WHERE id=? AND business_id=1", (_hash_password(new_password), user_id))
    changed = cur.rowcount > 0
    c.commit(); c.close()
    return changed

def update_business(name, profile):
    c = _conn()
    c.execute("UPDATE businesses SET name=?, profile=? WHERE id=1", (name, profile))
    c.commit(); c.close()

def _snapshot_process(p):
    return {
        "name": p.get("name", "Untitled Process"), "description": p.get("description", ""),
        "category": p.get("category", "Operations"), "owner": p.get("owner", "Business Owner"),
        "status": p.get("status", "Active"), "trigger": p.get("trigger", ""),
        "inputs": p.get("inputs", []), "roles": p.get("roles", []), "steps": p.get("steps", []),
        "decisions": p.get("decisions", []), "exceptions": p.get("exceptions", []),
        "output": p.get("output", ""), "tags": p.get("tags", []),
    }

def _save_version(c, process_id, p, user_id=0, changed_by="System", change_note=""):
    row = c.execute("SELECT COALESCE(MAX(version),0) FROM process_versions WHERE process_id=?", (process_id,)).fetchone()
    version = int(row[0] or 0) + 1
    c.execute("INSERT INTO process_versions (process_id,version,snapshot_json,changed_by_user_id,changed_by,change_note,created_at) VALUES (?,?,?,?,?,?,?)",
              (process_id, version, json.dumps(_snapshot_process(p)), user_id or 0, changed_by or "System", change_note or "", datetime.now().isoformat(timespec="seconds")))
    return version

def create_process(p, user_id=0, changed_by="System", change_note="Initial version"):
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    _insert_process(c, p, now)
    pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    _save_version(c, pid, p, user_id, changed_by, change_note)
    c.commit(); c.close()
    return pid

def update_process(pid, p, user_id=0, changed_by="System", change_note="Updated process"):
    """Update an existing process and create a new immutable SOP version."""
    if not pid:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    c.execute("""UPDATE processes SET
        name=?, description=?, category=?, owner=?, status=?, trigger=?,
        inputs_json=?, roles_json=?, steps_json=?, decisions_json=?,
        exceptions_json=?, output=?, tags_json=?, updated_at=?
        WHERE id=? AND business_id=1""",
        (p.get("name", "Untitled Process"), p.get("description", ""),
         p.get("category", "Operations"), p.get("owner", "Business Owner"),
         p.get("status", "Active"), p.get("trigger", ""),
         json.dumps(p.get("inputs", [])), json.dumps(p.get("roles", [])),
         json.dumps(p.get("steps", [])), json.dumps(p.get("decisions", [])),
         json.dumps(p.get("exceptions", [])), p.get("output", ""),
         json.dumps(p.get("tags", [])), now, pid))
    changed = c.execute("SELECT changes()").fetchone()[0] > 0
    if changed:
        _save_version(c, pid, p, user_id, changed_by, change_note)
    c.commit(); c.close()
    return changed

def get_process_versions(pid):
    c = _conn()
    rows = c.execute("SELECT * FROM process_versions WHERE process_id=? ORDER BY version DESC", (pid,)).fetchall()
    c.close()
    out=[]
    for r in rows:
        d=dict(r)
        try: d["snapshot"] = json.loads(d.pop("snapshot_json"))
        except Exception: d["snapshot"] = {}
        out.append(d)
    return out

def restore_process_version(pid, version, user_id=0, changed_by="System"):
    c = _conn()
    row = c.execute("SELECT snapshot_json FROM process_versions WHERE process_id=? AND version=?", (pid, version)).fetchone()
    c.close()
    if not row:
        return False
    p = json.loads(row[0])
    return update_process(pid, p, user_id, changed_by, f"Restored version {version}")

def delete_process(pid):
    """Permanently delete a process and all of its versions/indexed chunks."""
    if not pid:
        return False
    c = _conn()
    row = c.execute(
        "SELECT id FROM processes WHERE id=? AND business_id=1", (pid,)
    ).fetchone()
    if not row:
        c.close()
        return False

    # Remove indexed RAG chunks, version history, then the process itself.
    c.execute("DELETE FROM chunks WHERE source_type='process' AND source_id=? AND business_id=1", (pid,))
    c.execute("DELETE FROM process_versions WHERE process_id=?", (pid,))
    c.execute("DELETE FROM processes WHERE id=? AND business_id=1", (pid,))
    deleted = c.execute("SELECT changes()").fetchone()[0] > 0
    c.commit()
    c.close()
    return deleted

def get_process(pid):
    if not pid:
        return None
    c = _conn()
    row = c.execute("SELECT * FROM processes WHERE id=? AND business_id=1", (pid,)).fetchone()
    c.close()
    if not row:
        return None
    d = dict(row)
    for field in ["inputs","roles","steps","decisions","exceptions","tags"]:
        d[field] = json.loads(d[field+"_json"])
        del d[field+"_json"]
    return d

def list_processes():
    c = _conn()
    rows = c.execute(
        "SELECT * FROM processes WHERE business_id=1 ORDER BY updated_at DESC"
    ).fetchall()
    c.close()

    out = []

    for r in rows:
        d = dict(r)

        for field in [
            "inputs",
            "roles",
            "steps",
            "decisions",
            "exceptions",
            "tags",
        ]:
            json_field = field + "_json"

            if json_field in d:
                try:
                    d[field] = json.loads(d[json_field])
                except (TypeError, json.JSONDecodeError):
                    d[field] = []

                del d[json_field]

        out.append(d)

    return out

def list_knowledge():
    c = _conn()
    rows = c.execute("SELECT * FROM knowledge WHERE business_id=1 ORDER BY updated_at DESC").fetchall()
    c.close()
    out=[]
    for r in rows:
        d=dict(r); d["tags"]=json.loads(d["tags_json"]); out.append(d)
    return out

def create_knowledge(title, kind, description, source, tags, content):
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    c.execute("""INSERT INTO knowledge
    (business_id,title,type,description,source,status,tags_json,content,created_at,updated_at)
    VALUES (1,?,?,?,?,?,?,?,?,?)""",
    (title, kind, description, source, "Indexed", json.dumps(tags), content, now, now))
    kid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit(); c.close()
    return kid


def get_knowledge(knowledge_id):
    c = _conn()
    row = c.execute("SELECT * FROM knowledge WHERE business_id=1 AND id=?", (knowledge_id,)).fetchone()
    c.close()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d.get("tags_json") or "[]")
    return d

def update_knowledge(knowledge_id, title, kind, description, source, tags, content):
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    cur = c.execute(
        """UPDATE knowledge
           SET title=?, type=?, description=?, source=?, tags_json=?, content=?, status='Indexed', updated_at=?
           WHERE business_id=1 AND id=?""",
        (title, kind, description, source, json.dumps(tags or []), content, now, knowledge_id),
    )
    c.commit()
    changed = cur.rowcount > 0
    c.close()
    return changed

def delete_knowledge(knowledge_id):
    c = _conn()
    c.execute("DELETE FROM chunks WHERE source_type='knowledge' AND source_id=?", (knowledge_id,))
    cur = c.execute("DELETE FROM knowledge WHERE business_id=1 AND id=?", (knowledge_id,))
    c.commit()
    changed = cur.rowcount > 0
    c.close()
    return changed

def add_chunk(source_type, source_id, title, content, metadata=None):
    c=_conn()
    c.execute("""INSERT INTO chunks
    (business_id,source_type,source_id,title,content,metadata_json,created_at)
    VALUES (1,?,?,?,?,?,?)""",
    (source_type, source_id, title, content, json.dumps(metadata or {}), datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close()

def clear_chunks_for(source_type, source_id):
    c=_conn(); c.execute("DELETE FROM chunks WHERE source_type=? AND source_id=?", (source_type, source_id)); c.commit(); c.close()

def list_chunks():
    c=_conn()
    rows=c.execute("SELECT * FROM chunks WHERE business_id=1 ORDER BY id").fetchall()
    c.close()
    return [dict(r) for r in rows]

def log_activity(action, details="", user_name="System", business_id=1):
    c = _conn()
    actor = f"{user_name}: {details}" if user_name else details
    c.execute("INSERT INTO activity (business_id,action,details,created_at) VALUES (?,?,?,?)",
              (business_id, action, actor, datetime.now().strftime("%Y-%m-%d %H:%M")))
    c.commit(); c.close()

def get_activity(limit=20):
    c=_conn()
    rows=c.execute("SELECT * FROM activity WHERE business_id=1 ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def seed_operational_data():
    """Idempotently add small demo products/suppliers for operational workflows."""
    c = _conn()
    business_id = 1
    now = datetime.now().isoformat(timespec="seconds")
    products = [
        ("Pepsi", "pepsi,cola", 100.0, 25.0, 10.0, "unit"),
        ("Tissue", "tissue,tissues", 80.0, 30.0, 10.0, "pack"),
        ("Surf", "surf,washing powder", 350.0, 12.0, 5.0, "pack"),
        ("Flour", "flour,atta,aata,آٹا,اٹا", 180.0, 8.0, 10.0, "kg"),
        ("Sooji", "sooji,suji,semolina,سوجی", 220.0, 15.0, 5.0, "kg"),
        ("Sabun", "sabun,soap,صابن", 150.0, 20.0, 5.0, "piece"),
        ("Sugar", "sugar,cheeni,چینی", 170.0, 20.0, 5.0, "kg"),
        ("Papad", "papad,papadum,پاپڑ,پاپڑ", None, 10.0, 5.0, "pack"),
        ("Nimko", "nimko,nimco,نمکو", None, 10.0, 5.0, "pack"),
        ("Rice", "rice,chawal,چاول", 320.0, 18.0, 5.0, "kg"),
        ("Cooking Oil", "oil,cooking oil,tel,آئل,آئل,تیل", 650.0, 10.0, 3.0, "liter"),
    ]
    for name, aliases, price, stock, minimum, unit in products:
        c.execute("""INSERT OR IGNORE INTO products
            (business_id,name,aliases,price,stock_quantity,minimum_stock,unit,active,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,1,?,?)""",
            (business_id, name, aliases, price, stock, minimum, unit, now, now))
        # Merge built-in aliases into existing demo products without overwriting owner edits.
        row = c.execute("SELECT id,aliases FROM products WHERE business_id=? AND name=?", (business_id, name)).fetchone()
        if row:
            existing = [x.strip() for x in str(row["aliases"] or "").split(",") if x.strip()]
            merged = existing[:]
            for alias in str(aliases).split(","):
                alias = alias.strip()
                if alias and alias not in merged:
                    merged.append(alias)
            c.execute("UPDATE products SET aliases=?, updated_at=? WHERE id=? AND business_id=?", (",".join(merged), now, row["id"], business_id))

    suppliers = [
        ("ABC Distributor", "0300-0000000"),
        ("City Wholesale", "0311-0000000"),
    ]
    for name, contact in suppliers:
        c.execute("""INSERT OR IGNORE INTO suppliers
            (business_id,name,contact,active,created_at,updated_at)
            VALUES (?,?,?,1,?,?)""", (business_id, name, contact, now, now))

    abc_id = c.execute("SELECT id FROM suppliers WHERE business_id=? AND name=?", (business_id, "ABC Distributor")).fetchone()[0]
    city_id = c.execute("SELECT id FROM suppliers WHERE business_id=? AND name=?", (business_id, "City Wholesale")).fetchone()[0]
    flour_id = c.execute("SELECT id FROM products WHERE business_id=? AND name=?", (business_id, "Flour")).fetchone()[0]
    tissue_id = c.execute("SELECT id FROM products WHERE business_id=? AND name=?", (business_id, "Tissue")).fetchone()[0]
    surf_id = c.execute("SELECT id FROM products WHERE business_id=? AND name=?", (business_id, "Surf")).fetchone()[0]

    c.execute("INSERT OR IGNORE INTO supplier_products (supplier_id,product_id,supplier_product_name,supplier_price) VALUES (?,?,?,?)", (abc_id, flour_id, "Flour", 170.0))
    c.execute("INSERT OR IGNORE INTO supplier_products (supplier_id,product_id,supplier_product_name,supplier_price) VALUES (?,?,?,?)", (city_id, tissue_id, "Tissue", 72.0))
    c.execute("INSERT OR IGNORE INTO supplier_products (supplier_id,product_id,supplier_product_name,supplier_price) VALUES (?,?,?,?)", (city_id, surf_id, "Surf", 320.0))
    c.commit()
    c.close()


def _normalize_name(value):
    return " ".join(str(value or "").strip().split())


def _aliases_for(name, aliases=""):
    values=[]
    for raw in [name] + str(aliases or "").split(","):
        v=_normalize_name(raw)
        if v and v.lower() not in {x.lower() for x in values}:
            values.append(v)
    return ",".join(values)


def create_product(name, price=None, unit="unit", stock_quantity=0, minimum_stock=0, aliases="", business_id=1):
    name=_normalize_name(name)
    if not name:
        raise ValueError("Product name is required.")
    try:
        price_value = None if price in (None, "") else float(price)
        stock=float(stock_quantity or 0)
        minimum=float(minimum_stock or 0)
    except (TypeError, ValueError):
        raise ValueError("Price and stock must be valid numbers.")
    if price_value is not None and price_value < 0:
        raise ValueError("Price cannot be negative.")
    if stock < 0 or minimum < 0:
        raise ValueError("Stock values cannot be negative.")
    c=_conn(); now=datetime.now().isoformat(timespec="seconds")
    try:
        cur=c.execute("""INSERT INTO products
            (business_id,name,aliases,price,stock_quantity,minimum_stock,unit,active,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,1,?,?)""",
            (business_id,name,_aliases_for(name,aliases),price_value,stock,minimum,unit or "unit",now,now))
        c.commit(); return cur.lastrowid
    except sqlite3.IntegrityError:
        c.rollback(); raise ValueError(f"{name} already exists in your product list.")
    finally:
        c.close()


def update_product(product_id, name=None, price=None, unit=None, stock_quantity=None, minimum_stock=None, aliases=None, business_id=1):
    product=get_product_by_id(product_id,business_id)
    if not product: raise ValueError("Product not found.")
    new_name=_normalize_name(name if name is not None else product["name"])
    new_price=product["price"] if price is None else (None if price=="" else float(price))
    new_stock=product["stock_quantity"] if stock_quantity is None else float(stock_quantity)
    new_min=product["minimum_stock"] if minimum_stock is None else float(minimum_stock)
    new_unit=unit if unit is not None else product["unit"]
    new_aliases=_aliases_for(new_name, aliases if aliases is not None else product.get("aliases",""))
    if new_price is not None and new_price < 0: raise ValueError("Price cannot be negative.")
    if new_stock < 0 or new_min < 0: raise ValueError("Stock values cannot be negative.")
    c=_conn(); now=datetime.now().isoformat(timespec="seconds")
    try:
        c.execute("""UPDATE products SET name=?,aliases=?,price=?,stock_quantity=?,minimum_stock=?,unit=?,updated_at=?
                   WHERE id=? AND business_id=?""",(new_name,new_aliases,new_price,new_stock,new_min,new_unit or "unit",now,product_id,business_id))
        c.commit(); return True
    except sqlite3.IntegrityError:
        c.rollback(); raise ValueError("Another product already uses that name.")
    finally: c.close()


def bulk_add_products(names, business_id=1):
    created=[]; existing=[]
    for raw in names:
        name=_normalize_name(raw)
        if not name: continue
        if find_product(name,business_id):
            existing.append(name); continue
        try:
            create_product(name, price=None, business_id=business_id)
            created.append(name)
        except ValueError:
            existing.append(name)
    return {"created":created,"existing":existing}


def set_product_price(product_id, price, business_id=1):
    product=get_product_by_id(product_id,business_id)
    if not product: raise ValueError("Product not found.")
    if price is None or float(price) < 0: raise ValueError("Enter a valid non-negative price.")
    return update_product(product_id, price=float(price), business_id=business_id)


def add_business_memory(key, value, memory_type="fact", source="owner", confidence=1.0, business_id=1):
    key=_normalize_name(key); value=str(value or "").strip()
    if not key or not value: raise ValueError("Memory key and value are required.")
    c=_conn(); now=datetime.now().isoformat(timespec="seconds")
    c.execute("""INSERT INTO business_memory (business_id,memory_type,key,value,source,confidence,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(business_id,memory_type,key) DO UPDATE SET value=excluded.value,source=excluded.source,confidence=excluded.confidence,updated_at=excluded.updated_at""",
              (business_id,memory_type,key,value,source,float(confidence),now,now))
    c.commit(); c.close(); return True


def list_business_memory(business_id=1, limit=100):
    c=_conn(); rows=c.execute("SELECT * FROM business_memory WHERE business_id=? ORDER BY updated_at DESC LIMIT ?",(business_id,limit)).fetchall(); c.close(); return [dict(r) for r in rows]


def delete_business_memory(memory_id, business_id=1):
    c=_conn(); cur=c.execute("DELETE FROM business_memory WHERE id=? AND business_id=?",(memory_id,business_id)); c.commit(); ok=cur.rowcount>0; c.close(); return ok

def find_product(query, business_id=1):
    q = (query or "").strip().lower()
    if not q:
        return None
    c = _conn()
    rows = c.execute("SELECT * FROM products WHERE business_id=? AND active=1", (business_id,)).fetchall()
    c.close()
    for row in rows:
        aliases = [a.strip().lower() for a in (row["aliases"] or "").split(",") if a.strip()]
        if q == row["name"].lower() or q in aliases:
            return dict(row)
    for row in rows:
        if q in row["name"].lower() or any(q in a for a in [a.strip().lower() for a in (row["aliases"] or "").split(",") if a.strip()]):
            return dict(row)
    return None


def list_products(business_id=1):
    c = _conn(); rows = c.execute("SELECT * FROM products WHERE business_id=? AND active=1 ORDER BY name", (business_id,)).fetchall(); c.close(); return [dict(r) for r in rows]


def get_product_by_id(product_id, business_id=1):
    c = _conn(); row = c.execute("SELECT * FROM products WHERE id=? AND business_id=?", (product_id, business_id)).fetchone(); c.close(); return dict(row) if row else None


def find_supplier(name, business_id=1):
    q = (name or "").strip().lower()
    if not q: return None
    c = _conn(); row = c.execute("SELECT * FROM suppliers WHERE business_id=? AND active=1 AND lower(name)=?", (business_id, q)).fetchone()
    if not row: row = c.execute("SELECT * FROM suppliers WHERE business_id=? AND active=1 AND lower(name) LIKE ? ORDER BY name LIMIT 1", (business_id, f"%{q}%")).fetchone()
    c.close(); return dict(row) if row else None


def find_supplier_for_product(product_id, business_id=1):
    c = _conn(); row = c.execute("""SELECT s.*, sp.supplier_price FROM suppliers s
        JOIN supplier_products sp ON sp.supplier_id=s.id
        WHERE s.business_id=? AND s.active=1 AND sp.product_id=? ORDER BY s.name LIMIT 1""", (business_id, product_id)).fetchone(); c.close(); return dict(row) if row else None


def create_sale(transaction_ref, total, created_by=0, status="Confirmed", business_id=1):
    c = _conn()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        cur = c.execute(
            "INSERT INTO sales (business_id,transaction_ref,total,status,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (business_id, transaction_ref, float(total), status, created_by, now),
        )
        sale_id = cur.lastrowid
        c.commit()
        return sale_id
    finally:
        c.close()


def create_sale_items(sale_id, items, business_id=1):
    c = _conn()
    try:
        for item in items:
            c.execute(
                "INSERT INTO sale_items (sale_id,product_id,quantity,unit_price,subtotal) VALUES (?,?,?,?,?)",
                (sale_id, item["product_id"], item["quantity"], item["unit_price"], item["subtotal"]),
            )
            c.execute(
                "UPDATE products SET stock_quantity=stock_quantity-?, updated_at=? WHERE id=? AND business_id=?",
                (item["quantity"], datetime.now().isoformat(timespec="seconds"), item["product_id"], business_id),
            )
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def save_confirmed_sale(transaction_ref, total, items, created_by=0, business_id=1):
    """Atomically validate current DB prices/stock, save the sale, and deduct inventory."""
    if not items:
        raise ValueError("The cart is empty.")
    c = _conn()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        checked = []
        calculated_total = 0.0
        for item in items:
            product = c.execute(
                "SELECT id,name,price,stock_quantity,active FROM products WHERE id=? AND business_id=?",
                (int(item["product_id"]), business_id),
            ).fetchone()
            if not product or not product["active"]:
                raise ValueError("One of the selected products is no longer available.")
            quantity = float(item["quantity"])
            if quantity <= 0:
                raise ValueError(f"Quantity for {product['name']} must be greater than zero.")
            if quantity > float(product["stock_quantity"]):
                raise ValueError(f"Not enough stock for {product['name']}. Available: {product['stock_quantity']:g}.")
            if product["price"] is None:
                raise ValueError(f"Price for {product['name']} is not set. Add the price in Product Catalog first.")
            unit_price = float(product["price"])
            subtotal = round(quantity * unit_price, 2)
            calculated_total += subtotal
            checked.append((product, quantity, unit_price, subtotal))

        if round(float(total), 2) != round(calculated_total, 2):
            raise ValueError("The cart total changed. Please rebuild the cart before confirming the sale.")

        cur = c.execute(
            "INSERT INTO sales (business_id,transaction_ref,total,status,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (business_id, transaction_ref, round(calculated_total, 2), "Confirmed", created_by, now),
        )
        sale_id = cur.lastrowid
        for product, quantity, unit_price, subtotal in checked:
            c.execute(
                "INSERT INTO sale_items (sale_id,product_id,quantity,unit_price,subtotal) VALUES (?,?,?,?,?)",
                (sale_id, product["id"], quantity, unit_price, subtotal),
            )
            c.execute(
                "UPDATE products SET stock_quantity=stock_quantity-?, updated_at=? WHERE id=? AND business_id=? AND stock_quantity>=?",
                (quantity, now, product["id"], business_id, quantity),
            )
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise ValueError(f"Stock changed while confirming {product['name']}. Please try again.")
        c.commit()
        return sale_id
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def create_supplier_order(supplier_id, items, created_by=0, business_id=1):
    if not items:
        raise ValueError("Supplier order must contain at least one item.")
    c = _conn()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        supplier = c.execute(
            "SELECT id FROM suppliers WHERE id=? AND business_id=? AND active=1",
            (supplier_id, business_id),
        ).fetchone()
        if not supplier:
            raise ValueError("Supplier is not available for this business.")
        cur = c.execute(
            "INSERT INTO supplier_orders (business_id,supplier_id,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (business_id, supplier_id, "Draft", created_by, now, now),
        )
        order_id = cur.lastrowid
        for item in items:
            quantity = float(item.get("quantity", 0))
            if quantity <= 0:
                raise ValueError("Supplier order quantity must be greater than zero.")
            product = c.execute(
                "SELECT id FROM products WHERE id=? AND business_id=? AND active=1",
                (int(item["product_id"]), business_id),
            ).fetchone()
            if not product:
                raise ValueError("One of the supplier-order products is unavailable.")
            c.execute(
                "INSERT INTO supplier_order_items (supplier_order_id,product_id,quantity,unit_price) VALUES (?,?,?,?)",
                (order_id, product["id"], quantity, item.get("unit_price")),
            )
        c.commit()
        return order_id
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def save_receipt_verification(sale_id, status, extracted_receipt, mismatches, created_by=0, business_id=1):
    c=_conn(); now=datetime.now().isoformat(timespec="seconds")
    cur=c.execute("INSERT INTO receipt_verifications (business_id,sale_id,status,extracted_receipt_json,mismatches_json,created_by,created_at) VALUES (?,?,?,?,?,?,?)", (business_id,sale_id,status,json.dumps(extracted_receipt or {}),json.dumps(mismatches or []),created_by,now)); rid=cur.lastrowid; c.commit(); c.close(); return rid

# ---------- Operational reporting helpers ----------
def get_daily_operations(business_id=1):
    c = _conn()
    today = datetime.now().date().isoformat()
    low = c.execute("SELECT id,name,stock_quantity,minimum_stock,unit FROM products WHERE business_id=? AND active=1 AND stock_quantity<=minimum_stock ORDER BY name", (business_id,)).fetchall()
    sales_today = c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS total FROM sales WHERE business_id=? AND date(created_at)=?", (business_id,today)).fetchone()
    pending_orders = c.execute("SELECT COUNT(*) AS n FROM supplier_orders WHERE business_id=? AND status IN ('Draft','Pending Approval')", (business_id,)).fetchone()[0]
    recent = c.execute("SELECT id,transaction_ref,total,status,created_at FROM sales WHERE business_id=? ORDER BY id DESC LIMIT 8", (business_id,)).fetchall()
    c.close()
    return {
        "low_stock": [dict(r) for r in low],
        "sales_count": sales_today["n"],
        "sales_total": sales_today["total"],
        "pending_supplier_orders": pending_orders,
        "recent_sales": [dict(r) for r in recent],
    }


def get_sale(sale_id, business_id=1):
    c = _conn()
    sale = c.execute("SELECT * FROM sales WHERE id=? AND business_id=?", (sale_id,business_id)).fetchone()
    if not sale:
        c.close(); return None
    items = c.execute("""SELECT si.*, p.name, p.unit FROM sale_items si JOIN products p ON p.id=si.product_id WHERE si.sale_id=?""", (sale_id,)).fetchall()
    c.close()
    data = dict(sale); data["items"] = [dict(x) for x in items]
    return data


def list_supplier_orders(business_id=1, limit=20):
    c=_conn()
    rows=c.execute("""SELECT so.*, s.name AS supplier_name FROM supplier_orders so
        JOIN suppliers s ON s.id=so.supplier_id WHERE so.business_id=? ORDER BY so.id DESC LIMIT ?""", (business_id,limit)).fetchall()
    c.close(); return [dict(r) for r in rows]


def approve_supplier_order(order_id, approved_by=0, business_id=1):
    c=_conn(); now=datetime.now().isoformat(timespec="seconds")
    cur=c.execute("UPDATE supplier_orders SET status='Approved', approved_by=?, updated_at=? WHERE id=? AND business_id=? AND status IN ('Draft','Pending Approval')", (approved_by,now,order_id,business_id))
    c.commit(); ok=cur.rowcount>0; c.close(); return ok
