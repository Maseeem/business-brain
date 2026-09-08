import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("business_brain.db")

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        profile TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS processes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT DEFAULT 'Operations',
        owner TEXT DEFAULT 'Business Owner',
        status TEXT DEFAULT 'Active',
        trigger TEXT DEFAULT '',
        inputs_json TEXT DEFAULT '[]',
        roles_json TEXT DEFAULT '[]',
        steps_json TEXT DEFAULT '[]',
        decisions_json TEXT DEFAULT '[]',
        exceptions_json TEXT DEFAULT '[]',
        output TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        type TEXT DEFAULT 'Document',
        description TEXT DEFAULT '',
        source TEXT DEFAULT '',
        status TEXT DEFAULT 'Indexed',
        tags_json TEXT DEFAULT '[]',
        content TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        source_type TEXT NOT NULL,
        source_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)
    c.commit()
    c.close()

def seed_demo_data():
    c = _conn()
    existing = c.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    if existing:
        c.close()
        return

    now = datetime.now().isoformat(timespec="seconds")
    c.execute("INSERT INTO businesses (id,name,profile,created_at) VALUES (1,?,?,?)",
              ("Nova Bakery", "A neighborhood bakery specializing in fresh bread, celebration cakes, and custom orders.", now))

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

    c.commit()
    c.close()

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

def update_business(name, profile):
    c = _conn()
    c.execute("UPDATE businesses SET name=?, profile=? WHERE id=1", (name, profile))
    c.commit(); c.close()

def create_process(p):
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    _insert_process(c, p, now)
    pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit(); c.close()
    return pid

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
    rows = c.execute("SELECT * FROM processes WHERE business_id=1 ORDER BY updated_at DESC").fetchall()
    c.close()
    out=[]
    for r in rows:
        d=dict(r)
        d["tags"]=json.loads(d["tags_json"])
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
    VALUES (1,?,?,?,?,?,?,?,?)""",
    (title, kind, description, source, "Indexed", json.dumps(tags), content, now, now))
    kid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit(); c.close()
    return kid

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

def log_activity(action, details=""):
    c=_conn()
    c.execute("INSERT INTO activity (business_id,action,details,created_at) VALUES (1,?,?,?)",
              (action, details, datetime.now().strftime("%Y-%m-%d %H:%M")))
    c.commit(); c.close()

def get_activity(limit=20):
    c=_conn()
    rows=c.execute("SELECT * FROM activity WHERE business_id=1 ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]
