from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional


DB_PATH = os.getenv("BUSINESS_BRAIN_DB", "business_brain.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            purpose TEXT DEFAULT '',
            trigger TEXT DEFAULT '',
            inputs TEXT DEFAULT '',
            roles TEXT DEFAULT '',
            steps TEXT DEFAULT '',
            decisions TEXT DEFAULT '',
            output TEXT DEFAULT '',
            exceptions TEXT DEFAULT '',
            warnings TEXT DEFAULT '',
            tools TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            type TEXT DEFAULT 'Note',
            description TEXT DEFAULT '',
            content TEXT DEFAULT '',
            source TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def seed_demo_data():
    conn = get_connection()
    cur = conn.cursor()

    business = cur.execute(
        "SELECT id FROM businesses LIMIT 1"
    ).fetchone()

    if business:
        business_id = business["id"]
    else:
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

    process_count = cur.execute(
        "SELECT COUNT(*) AS count FROM processes WHERE business_id = ?",
        (business_id,),
    ).fetchone()["count"]

    if process_count == 0:
        demo_processes = [
            {
                "name": "New Customer Order",
                "purpose": "Process a standard bakery customer order.",
                "trigger": "Customer requests bakery products.",
                "inputs": "Customer name, contact details, product, quantity, required date.",
                "roles": "Customer, bakery staff.",
                "steps": [
                    "Receive the customer request.",
                    "Confirm product and quantity.",
                    "Check required date and availability.",
                    "Confirm price with the customer.",
                    "Record the order.",
                    "Confirm the order with the customer."
                ],
                "decisions": [
                    "Is the requested product available?",
                    "Can the requested date be fulfilled?"
                ],
                "output": "Confirmed customer order.",
                "exceptions": [
                    "Requested product unavailable.",
                    "Requested date unavailable."
                ],
                "warnings": "Confirm important order details before final confirmation.",
                "tools": "Order record and customer communication."
            },
            {
                "name": "Custom Cake Order",
                "purpose": "Handle custom cake requests.",
                "trigger": "Customer requests a custom cake.",
                "inputs": "Cake size, flavor, design, message, event date, customer details.",
                "roles": "Customer, bakery staff, cake decorator.",
                "steps": [
                    "Collect cake requirements.",
                    "Confirm design and flavor.",
                    "Confirm availability for the event date.",
                    "Calculate the price.",
                    "Collect the required advance payment.",
                    "Confirm the order."
                ],
                "decisions": [
                    "Is the requested design possible?",
                    "Is the event date available?"
                ],
                "output": "Confirmed custom cake order.",
                "exceptions": [
                    "Design cannot be fulfilled.",
                    "Date is unavailable."
                ],
                "warnings": "Custom cake orders require a 50% advance payment.",
                "tools": "Order record and customer communication."
            },
            {
                "name": "Inventory Restocking",
                "purpose": "Restock ingredients and bakery supplies.",
                "trigger": "Inventory falls below the required level.",
                "inputs": "Current stock, minimum stock level, supplier information.",
                "roles": "Bakery staff, supplier.",
                "steps": [
                    "Check current inventory.",
                    "Identify items below minimum level.",
                    "Prepare the restocking list.",
                    "Contact supplier.",
                    "Place the order.",
                    "Update inventory after delivery."
                ],
                "decisions": [
                    "Is the item below the minimum stock level?",
                    "Is the supplier able to provide the item?"
                ],
                "output": "Restocked inventory.",
                "exceptions": [
                    "Supplier cannot provide an item.",
                    "Delivery is delayed."
                ],
                "warnings": "Check stock before placing duplicate orders.",
                "tools": "Inventory records and supplier information."
            },
            {
                "name": "Customer Complaint Handling",
                "purpose": "Handle customer complaints consistently.",
                "trigger": "Customer submits a complaint.",
                "inputs": "Customer details, order details, complaint description.",
                "roles": "Customer, bakery staff, manager.",
                "steps": [
                    "Receive the complaint.",
                    "Review the order details.",
                    "Understand the issue.",
                    "Determine the appropriate resolution.",
                    "Communicate the resolution to the customer.",
                    "Record the outcome."
                ],
                "decisions": [
                    "Does the complaint qualify for a refund or replacement?",
                    "Does the issue require manager review?"
                ],
                "output": "Resolved and recorded complaint.",
                "exceptions": [
                    "Complaint requires manager approval."
                ],
                "warnings": "Follow the refund policy when offering refunds.",
                "tools": "Order records and customer communication."
            },
        ]

        for p in demo_processes:
            cur.execute(
                """
                INSERT INTO processes (
                    business_id,
                    name,
                    purpose,
                    trigger,
                    inputs,
                    roles,
                    steps,
                    decisions,
                    output,
                    exceptions,
                    warnings,
                    tools
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    p["name"],
                    p["purpose"],
                    p["trigger"],
                    p["inputs"],
                    p["roles"],
                    "\n".join(
                        f"{i + 1}. {step}"
                        for i, step in enumerate(p["steps"])
                    ),
                    "\n".join(
                        f"- {item}"
                        for item in p["decisions"]
                    ),
                    p["output"],
                    "\n".join(
                        f"- {item}"
                        for item in p["exceptions"]
                    ),
                    p["warnings"],
                    p["tools"],
                ),
            )

    knowledge_count = cur.execute(
        "SELECT COUNT(*) AS count FROM knowledge WHERE business_id = ?",
        (business_id,),
    ).fetchone()["count"]

    if knowledge_count == 0:
        demo_knowledge = [
            (
                "Customer Service Policy",
                "Policy",
                "Basic customer service guidelines.",
                "Customers should be treated respectfully and staff should confirm important order details before finalizing an order.",
                "Nova Bakery",
                "Active",
                "customer,service,policy",
            ),
            (
                "Pricing Guide",
                "Guide",
                "Basic pricing guidance.",
                "Prices should be confirmed with the customer before an order is finalized. Custom products may have additional charges.",
                "Nova Bakery",
                "Active",
                "pricing,orders",
            ),
            (
                "Order Requirements",
                "Policy",
                "Information required for customer orders.",
                "Orders should include customer contact details, product or cake requirements, quantity, and required date.",
                "Nova Bakery",
                "Active",
                "orders,requirements",
            ),
            (
                "Refund Policy",
                "Policy",
                "Guidelines for handling refunds.",
                "Refund requests should be reviewed against the order details and applicable bakery policy. Escalate unusual cases to the manager.",
                "Nova Bakery",
                "Active",
                "refund,customer,policy",
            ),
        ]

        for item in demo_knowledge:
            cur.execute(
                """
                INSERT INTO knowledge (
                    business_id,
                    title,
                    type,
                    description,
                    content,
                    source,
                    status,
                    tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                    item[5],
                    item[6],
                ),
            )

    conn.commit()
    conn.close()


def get_business(business_id: int = 1) -> Optional[Dict[str, Any]]:
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM businesses
        WHERE id = ?
        """,
        (business_id,),
    ).fetchone()

    conn.close()

    return dict(row) if row else None


def list_processes(
    business_id: int = 1,
) -> List[Dict[str, Any]]:
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM processes
        WHERE business_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (business_id,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_process(
    process_id: int,
) -> Optional[Dict[str, Any]]:
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

    return dict(row) if row else None


def create_process(
    business_id: int,
    sop: Dict[str, Any],
) -> int:

    conn = get_connection()

    cur = conn.cursor()

    def as_text(value):
        if isinstance(value, list):
            return "\n".join(
                f"{i + 1}. {item}"
                for i, item in enumerate(value)
            )

        if isinstance(value, dict):
            return "\n".join(
                f"{key}: {val}"
                for key, val in value.items()
            )

        return str(value or "")

    cur.execute(
        """
        INSERT INTO processes (
            business_id,
            name,
            purpose,
            trigger,
            inputs,
            roles,
            steps,
            decisions,
            output,
            exceptions,
            warnings,
            tools
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business_id,
            sop.get("name", "Untitled Process"),
            as_text(sop.get("purpose")),
            as_text(sop.get("trigger")),
            as_text(sop.get("inputs")),
            as_text(sop.get("roles")),
            as_text(sop.get("steps")),
            as_text(sop.get("decisions")),
            as_text(sop.get("output")),
            as_text(sop.get("exceptions")),
            as_text(sop.get("warnings")),
            as_text(sop.get("tools")),
        ),
    )

    process_id = cur.lastrowid

    conn.commit()
    conn.close()

    return int(process_id)


def create_knowledge(
    business_id: int,
    title: str,
    type: str = "Note",
    description: str = "",
    content: str = "",
    source: str = "",
    status: str = "Active",
    tags: str = "",
) -> int:

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO knowledge (
            business_id,
            title,
            type,
            description,
            content,
            source,
            status,
            tags
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business_id,
            title,
            type,
            description,
            content,
            source,
            status,
            tags,
        ),
    )

    knowledge_id = cur.lastrowid

    conn.commit()
    conn.close()

    return int(knowledge_id)


def get_knowledge(
    knowledge_id: int,
) -> Optional[Dict[str, Any]]:
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

    return dict(row) if row else None


def list_knowledge(
    business_id: int = 1,
) -> List[Dict[str, Any]]:
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM knowledge
        WHERE business_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (business_id,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def add_chunk(
    source_id: int,
    chunk_index: int,
    content: str,
) -> int:

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO chunks (
            source_id,
            chunk_index,
            content
        )
        VALUES (?, ?, ?)
        """,
        (
            source_id,
            chunk_index,
            content,
        ),
    )

    chunk_id = cur.lastrowid

    conn.commit()
    conn.close()

    return int(chunk_id)


def delete_chunks_for_source(
    source_id: int,
):
    conn = get_connection()

    conn.execute(
        """
        DELETE FROM chunks
        WHERE source_id = ?
        """,
        (source_id,),
    )

    conn.commit()
    conn.close()


def list_chunks(
    source_id: Optional[int] = None,
) -> List[Dict[str, Any]]:

    conn = get_connection()

    if source_id is None:
        rows = conn.execute(
            """
            SELECT
                chunks.*,
                knowledge.title,
                knowledge.type
            FROM chunks
            LEFT JOIN knowledge
                ON knowledge.id = chunks.source_id
            ORDER BY chunks.source_id, chunks.chunk_index
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                chunks.*,
                knowledge.title,
                knowledge.type
            FROM chunks
            LEFT JOIN knowledge
                ON knowledge.id = chunks.source_id
            WHERE chunks.source_id = ?
            ORDER BY chunks.chunk_index
            """,
            (source_id,),
        ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def log_activity(
    business_id: int,
    action: str,
    details: str = "",
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO activity (
            business_id,
            action,
            details
        )
        VALUES (?, ?, ?)
        """,
        (
            business_id,
            action,
            details,
        ),
    )

    conn.commit()
    conn.close()


def list_activity(
    business_id: int = 1,
    limit: int = 50,
) -> List[Dict[str, Any]]:

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM activity
        WHERE business_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (
            business_id,
            limit,
        ),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_activity(
    business_id: int = 1,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    return list_activity(
        business_id=business_id,
        limit=limit,
    )


# Initialize database when the module is loaded.
init_db()
seed_demo_data()
