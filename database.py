import sqlite3
import json
from datetime import datetime
from pathlib import Pat

DB_PATH = Path("business_brain.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            process_name TEXT NOT NULL,
            category TEXT DEFAULT '',
            purpose TEXT DEFAULT '',
            trigger TEXT DEFAULT '',
            required_inputs TEXT DEFAULT '[]',
            roles TEXT DEFAULT '[]',
            steps TEXT DEFAULT '[]',
            decisions TEXT DEFAULT '[]',
            exceptions TEXT DEFAULT '[]',
            output TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            knowledge_type TEXT DEFAULT 'Note',
            description TEXT DEFAULT '',
            source TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            tags TEXT DEFAULT '[]',
            content TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def seed_demo_data():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM businesses")
    count = cur.fetchone()[0]

    if count == 0:
        cur.execute(
            """
            INSERT INTO businesses (name, description)
            VALUES (?, ?)
            """,
            (
                "Nova Bakery",
                "A demo bakery business used to demonstrate Business Brain.",
            ),
        )

        business_id = cur.lastrowid

        processes = [
            {
                "process_name": "New Customer Order",
                "category": "Sales",
                "purpose": "Capture and confirm a new bakery order.",
                "trigger": "A customer contacts Nova Bakery to place an order.",
                "required_inputs": [
                    "Customer name",
                    "Phone number",
                    "Product",
                    "Quantity",
                    "Pickup date",
                ],
                "roles": ["Staff member"],
                "steps": [
                    {
                        "action": "Collect customer and order information.",
                        "notes": "",
                    },
                    {
                        "action": "Check product availability.",
                        "notes": "",
                    },
                    {
                        "action": "Confirm price and pickup details.",
                        "notes": "",
                    },
                    {
                        "action": "Record the confirmed order.",
                        "notes": "",
                    },
                ],
                "decisions": [
                    "If the requested product is unavailable, confirm an alternative."
                ],
                "exceptions": [],
                "output": "Confirmed customer order",
                "tags": ["orders", "sales"],
            },
            {
                "process_name": "Custom Cake Order",
                "category": "Sales",
                "purpose": "Handle custom cake requests.",
                "trigger": "A customer requests a custom cake.",
                "required_inputs": [
                    "Customer name",
                    "Phone number",
                    "Cake type",
                    "Size",
                    "Flavor",
                    "Quantity",
                    "Required date",
                    "Special requirements",
                ],
                "roles": ["Staff member"],
                "steps": [
                    {
                        "action": "Collect the customer's cake requirements.",
                        "notes": "",
                    },
                    {
                        "action": "Check availability.",
                        "notes": "",
                    },
                    {
                        "action": "Confirm the price with the customer.",
                        "notes": "",
                    },
                    {
                        "action": "Record the confirmed order.",
                        "notes": "",
                    },
                ],
                "decisions": [],
                "exceptions": [],
                "output": "Confirmed custom cake order",
                "tags": ["cake", "custom-order"],
            },
            {
                "process_name": "Inventory Restocking",
                "category": "Operations",
                "purpose": "Restock bakery ingredients and supplies.",
                "trigger": "Inventory levels fall below the required level.",
                "required_inputs": [
                    "Current inventory",
                    "Required stock level",
                    "Supplier information",
                ],
                "roles": ["Staff member"],
                "steps": [
                    {
                        "action": "Review current inventory.",
                        "notes": "",
                    },
                    {
                        "action": "Identify items requiring restocking.",
                        "notes": "",
                    },
                    {
                        "action": "Prepare the supplier order.",
                        "notes": "",
                    },
                    {
                        "action": "Record the restocking activity.",
                        "notes": "",
                    },
                ],
                "decisions": [],
                "exceptions": [],
                "output": "Updated inventory",
                "tags": ["inventory", "operations"],
            },
            {
                "process_name": "Customer Complaint Handling",
                "category": "Customer Service",
                "purpose": "Handle and resolve customer complaints.",
                "trigger": "A customer submits a complaint.",
                "required_inputs": [
                    "Customer details",
                    "Order details",
                    "Complaint details",
                ],
                "roles": ["Staff member"],
                "steps": [
                    {
                        "action": "Listen to and record the complaint.",
                        "notes": "",
                    },
                    {
                        "action": "Review the relevant order information.",
                        "notes": "",
                    },
                    {
                        "action": "Determine the appropriate response.",
                        "notes": "",
                    },
                    {
                        "action": "Record the resolution.",
                        "notes": "",
                    },
                ],
                "decisions": [],
                "exceptions": [],
                "output": "Resolved or escalated complaint",
                "tags": ["complaints", "customer-service"],
            },
        ]

        for p in processes:
            now = datetime.utcnow().isoformat()

            cur.execute(
                """
                INSERT INTO processes (
                    business_id,
                    process_name,
                    category,
                    purpose,
                    trigger,
                    required_inputs,
                    roles,
                    steps,
                    decisions,
                    exceptions,
                    output,
                    tags,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    p["process_name"],
                    p["category"],
                    p["purpose"],
                    p["trigger"],
                    json.dumps(p["required_inputs"]),
                    json.dumps(p["roles"]),
                    json.dumps(p["steps"]),
                    json.dumps(p["decisions"]),
                    json.dumps(p["exceptions"]),
                    p["output"],
                    json.dumps(p["tags"]),
                    now,
                    now,
                ),
            )

        knowledge_items = [
            (
                "Customer Service Policy",
                "Policy",
                "Guidance for customer service interactions.",
                "demo",
                "active",
                ["customer-service"],
                "Staff should communicate clearly and professionally with customers.",
            ),
            (
                "Pricing Guide",
                "Guide",
                "Basic pricing information.",
                "demo",
                "active",
                ["pricing"],
                "Prices should be confirmed with the customer before the order is finalized.",
            ),
            (
                "Order Requirements",
                "Guide",
                "Information needed for bakery orders.",
                "demo",
                "active",
                ["orders"],
                "New orders require the customer's name, phone number, product, quantity, and pickup date.",
            ),
            (
                "Refund Policy",
                "Policy",
                "General refund guidance.",
                "demo",
                "active",
                ["refunds"],
                "Refund decisions should follow the bakery's approved refund policy.",
            ),
        ]

        for item in knowledge_items:
            cur.execute(
                """
                INSERT INTO knowledge (
                    business_id,
                    title,
                    knowledge_type,
                    description,
                    source,
                    status,
                    tags,
                    content,
                    created_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                    json.dumps(item[5]),
                    item[6],
                    datetime.utcnow().isoformat(),
                ),
            )

        conn.commit()

    conn.close()


def create_process(process):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT INTO processes (
            business_id,
            process_name,
            category,
            purpose,
            trigger,
            required_inputs,
            roles,
            steps,
            decisions,
            exceptions,
            output,
            tags,
            created_at,
            updated_at
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            process.get("process_name", "Untitled Process"),
            process.get("category", ""),
            process.get("purpose", ""),
            process.get("trigger", ""),
            json.dumps(process.get("required_inputs", [])),
            json.dumps(process.get("roles", [])),
            json.dumps(process.get("steps", [])),
            json.dumps(process.get("decisions", [])),
            json.dumps(process.get("exceptions", [])),
            process.get("output", ""),
            json.dumps(process.get("tags", [])),
            now,
            now,
        ),
    )

    process_id = cur.lastrowid

    conn.commit()
    conn.close()

    return process_id


def get_process(process_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM processes
        WHERE id = ?
        """,
        (process_id,),
    ).fetchone()

    conn.close()

    if not row:
        return None

    data = dict(row)

    for field in [
        "required_inputs",
        "roles",
        "steps",
        "decisions",
        "exceptions",
        "tags",
    ]:
        try:
            data[field] = json.loads(data[field])
        except Exception:
            data[field] = []

    return data


def list_processes():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM processes
        WHERE business_id = 1
        ORDER BY updated_at DESC
        """
    ).fetchall()

    conn.close()

    result = []

    for row in rows:
        data = dict(row)

        for field in [
            "required_inputs",
            "roles",
            "steps",
            "decisions",
            "exceptions",
            "tags",
        ]:
            try:
                data[field] = json.loads(data[field])
            except Exception:
                data[field] = []

        result.append(data)

    return result


def create_knowledge(
    title,
    knowledge_type,
    description,
    source,
    status,
    tags,
    content,
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO knowledge (
            business_id,
            title,
            knowledge_type,
            description,
            source,
            status,
            tags,
            content,
            created_at
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            knowledge_type,
            description,
            source,
            status,
            json.dumps(tags or []),
            content,
            datetime.utcnow().isoformat(),
        ),
    )

    knowledge_id = cur.lastrowid

    conn.commit()
    conn.close()

    return knowledge_id


def get_knowledge(knowledge_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM knowledge
        WHERE id = ?
        """,
        (knowledge_id,),
    ).fetchone()

    conn.close()

    if not row:
        return None

    data = dict(row)

    try:
        data["tags"] = json.loads(data.get("tags", "[]"))
    except Exception:
        data["tags"] = []

    return data


def list_knowledge():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM knowledge
        WHERE business_id = 1
        ORDER BY created_at DESC
        """
    ).fetchall()

    conn.close()

    result = []

    for row in rows:
        data = dict(row)

        try:
            data["tags"] = json.loads(data.get("tags", "[]"))
        except Exception:
            data["tags"] = []

        result.append(data)

    return result


def add_chunk(
    source_type,
    source_id,
    title,
    content,
):
    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO chunks (
            business_id,
            source_type,
            source_id,
            title,
            content,
            created_at
        )
        VALUES (1, ?, ?, ?, ?, ?)
        """,
        (
            source_type,
            source_id,
            title,
            content,
            datetime.utcnow().isoformat(),
        ),
    )

    chunk_id = cur.lastrowid

    conn.commit()
    conn.close()

    return chunk_id


def delete_chunks_for_source(source_type, source_id):
    conn = get_connection()

    conn.execute(
        """
        DELETE FROM chunks
        WHERE business_id = 1
        AND source_type = ?
        AND source_id = ?
        """,
        (
            source_type,
            source_id,
        ),
    )

    conn.commit()
    conn.close()


def list_chunks():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM chunks
        WHERE business_id = 1
        ORDER BY id
        """
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def log_activity(action, details=""):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO activity (
            business_id,
            action,
            details,
            created_at
        )
        VALUES (1, ?, ?, ?)
        """,
        (
            action,
            details,
            datetime.utcnow().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def list_activity(limit=50):
    def get_activity(limit=50):
    return list_activity(limit)
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM activity
        WHERE business_id = 1
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


init_db()
seed_demo_data()
