"""Store of custom items a BD user has promoted from a one-off
"client-requested" product into the real catalog.

Backed by Postgres (Neon, free tier) when DATABASE_URL is set - this is what
makes "Make permanent" survive a real redeploy, not just a server restart.
Falls back to the original file-backed JSON store (same no-database
convention as stats.py) when DATABASE_URL is absent, e.g. local dev.

Deliberately kept separate from the main catalog cache (data_provider.py) -
that cache is a raw byte-blob of an uploaded spreadsheet, re-serializing it
just to append one row would need a new writer with real round-trip risk to
the primary catalog. This store is merged into the product list at read time
instead (see app.py) - promoted items are always the base catalog plus
whatever's in here.
"""

import json
import os
import threading
from pathlib import Path

try:
    from . import db
    from .models import CustomProduct, Product
except ImportError:
    import db
    from models import CustomProduct, Product

ROOT = Path(__file__).resolve().parent.parent
PROMOTED_PRODUCTS_PATH = Path(
    os.environ.get("PROMOTED_PRODUCTS_PATH", str(ROOT / ".cache" / "promoted_products.json"))
)

_LOCK = threading.Lock()


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS promoted_products (
                name TEXT PRIMARY KEY,
                price NUMERIC NOT NULL,
                category TEXT NOT NULL
            )
            """
        )
    conn.commit()


def _db_load() -> list[dict]:
    conn = db.get_connection()
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT name, price, category FROM promoted_products")
            rows = cur.fetchall()
        return [{"name": row[0], "price": float(row[1]), "category": row[2]} for row in rows]
    finally:
        conn.close()


def _db_add(item: CustomProduct) -> None:
    conn = db.get_connection()
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO promoted_products (name, price, category) VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET price = EXCLUDED.price, category = EXCLUDED.category
                """,
                (item.name, item.price, item.category),
            )
        conn.commit()
    finally:
        conn.close()


def _file_load() -> list[dict]:
    if PROMOTED_PRODUCTS_PATH.exists():
        try:
            data = json.loads(PROMOTED_PRODUCTS_PATH.read_text())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _file_add(item: CustomProduct) -> None:
    data = _file_load()
    data.append({"name": item.name, "price": item.price, "category": item.category})
    PROMOTED_PRODUCTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMOTED_PRODUCTS_PATH.write_text(json.dumps(data))


def _load() -> list[dict]:
    with _LOCK:
        return _db_load() if db.is_configured() else _file_load()


def get_promoted_products() -> list[Product]:
    return [Product(name=row["name"], selling_price=row["price"], category=row["category"]) for row in _load()]


def is_name_taken(name: str, catalog_products: list[Product]) -> bool:
    normalized = name.strip().lower()
    promoted_names = {row["name"].strip().lower() for row in _load()}
    catalog_names = {product.name.strip().lower() for product in catalog_products}
    return normalized in promoted_names or normalized in catalog_names


def add_promoted_product(item: CustomProduct) -> None:
    with _LOCK:
        if db.is_configured():
            _db_add(item)
        else:
            _file_add(item)
