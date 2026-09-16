"""Store of custom hamper items a BD user has promoted from a one-off
"client-requested" item into the real catalog. Sibling of
backend/promoted_products.py (kept separate per the existing
snack_boxes/hampers domain split - see PHASE1_HAMPERS.md), same Postgres-
when-DATABASE_URL-is-set / file-fallback pattern.

Merged into the item list at read time in hampers/api.py, not written into
the hamper catalog cache file - same reasoning as the snack-box version:
that cache is a raw byte-blob of an uploaded spreadsheet, not a place to
append one row into safely.
"""

import json
import os
import threading
from pathlib import Path

try:
    from .models import HamperCustomItem, HamperItem
except ImportError:
    from models import HamperCustomItem, HamperItem

try:
    from .. import db
except ImportError:
    import db

ROOT = Path(__file__).resolve().parent.parent.parent
PROMOTED_ITEMS_PATH = Path(
    os.environ.get("PROMOTED_HAMPER_ITEMS_PATH", str(ROOT / ".cache" / "promoted_hamper_items.json"))
)

_LOCK = threading.Lock()


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS promoted_hamper_items (
                name TEXT PRIMARY KEY,
                price NUMERIC NOT NULL,
                category TEXT NOT NULL,
                length_in NUMERIC,
                breadth_in NUMERIC,
                height_in NUMERIC
            )
            """
        )
    conn.commit()


def _db_load() -> list[dict]:
    conn = db.get_connection()
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT name, price, category, length_in, breadth_in, height_in FROM promoted_hamper_items")
            rows = cur.fetchall()
        return [
            {
                "name": row[0],
                "price": float(row[1]),
                "category": row[2],
                "length_in": float(row[3]) if row[3] is not None else None,
                "breadth_in": float(row[4]) if row[4] is not None else None,
                "height_in": float(row[5]) if row[5] is not None else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def _db_add(item: HamperCustomItem) -> None:
    conn = db.get_connection()
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO promoted_hamper_items
                    (name, price, category, length_in, breadth_in, height_in)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    price = EXCLUDED.price,
                    category = EXCLUDED.category,
                    length_in = EXCLUDED.length_in,
                    breadth_in = EXCLUDED.breadth_in,
                    height_in = EXCLUDED.height_in
                """,
                (item.name, item.price, item.category, item.length_in, item.breadth_in, item.height_in),
            )
        conn.commit()
    finally:
        conn.close()


def _file_load() -> list[dict]:
    if PROMOTED_ITEMS_PATH.exists():
        try:
            data = json.loads(PROMOTED_ITEMS_PATH.read_text())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _file_add(item: HamperCustomItem) -> None:
    data = _file_load()
    data.append({
        "name": item.name,
        "price": item.price,
        "category": item.category,
        "length_in": item.length_in,
        "breadth_in": item.breadth_in,
        "height_in": item.height_in,
    })
    PROMOTED_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMOTED_ITEMS_PATH.write_text(json.dumps(data))


def _load() -> list[dict]:
    with _LOCK:
        return _db_load() if db.is_configured() else _file_load()


def get_promoted_items() -> list[HamperItem]:
    return [
        HamperItem(
            name=row["name"],
            price=row["price"],
            category=row["category"],
            length_in=row.get("length_in"),
            breadth_in=row.get("breadth_in"),
            height_in=row.get("height_in"),
        )
        for row in _load()
    ]


def is_name_taken(name: str, catalog_items: list[HamperItem]) -> bool:
    normalized = name.strip().lower()
    promoted_names = {row["name"].strip().lower() for row in _load()}
    catalog_names = {item.name.strip().lower() for item in catalog_items}
    return normalized in promoted_names or normalized in catalog_names


def add_promoted_item(item: HamperCustomItem) -> None:
    with _LOCK:
        if db.is_configured():
            _db_add(item)
        else:
            _file_add(item)
