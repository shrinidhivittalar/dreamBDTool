"""Lightweight, file-backed store of custom items a BD user has promoted
from a one-off "client-requested" product into the real catalog. Same
no-database convention as stats.py and the product-catalog cache: an
in-memory-on-read list flushed to a JSON file on every change, guarded by a
lock for concurrent-request safety.

Deliberately kept separate from the main catalog cache (data_provider.py) -
that cache is a raw byte-blob of an uploaded spreadsheet, re-serializing it
just to append one row would need a new writer with real round-trip risk to
the primary catalog. This file is merged into the product list at read time
instead (see app.py) - promoted items are always the base catalog plus
whatever's in here.

Same caveat as everything else with no persistent disk attached: survives a
plain server restart, not an actual redeploy. Surfaced to the BD user
directly in the "Make permanent" confirmation copy in the frontend, not
just here.
"""

import json
import os
import threading
from pathlib import Path

try:
    from .models import CustomProduct, Product
except ImportError:
    from models import CustomProduct, Product

ROOT = Path(__file__).resolve().parent.parent
PROMOTED_PRODUCTS_PATH = Path(
    os.environ.get("PROMOTED_PRODUCTS_PATH", str(ROOT / ".cache" / "promoted_products.json"))
)

_LOCK = threading.Lock()


def _load() -> list[dict]:
    if PROMOTED_PRODUCTS_PATH.exists():
        try:
            data = json.loads(PROMOTED_PRODUCTS_PATH.read_text())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save(data: list[dict]) -> None:
    PROMOTED_PRODUCTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMOTED_PRODUCTS_PATH.write_text(json.dumps(data))


def get_promoted_products() -> list[Product]:
    with _LOCK:
        return [Product(name=row["name"], selling_price=row["price"], category=row["category"]) for row in _load()]


def is_name_taken(name: str, catalog_products: list[Product]) -> bool:
    normalized = name.strip().lower()
    with _LOCK:
        promoted_names = {row["name"].strip().lower() for row in _load()}
    catalog_names = {product.name.strip().lower() for product in catalog_products}
    return normalized in promoted_names or normalized in catalog_names


def add_promoted_product(item: CustomProduct) -> None:
    with _LOCK:
        data = _load()
        data.append({"name": item.name, "price": item.price, "category": item.category})
        _save(data)
