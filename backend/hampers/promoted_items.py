"""Lightweight, file-backed store of custom hamper items a BD user has
promoted from a one-off "client-requested" item into the real catalog.
Sibling of backend/promoted_products.py (kept separate per the existing
snack_boxes/hampers domain split - see PHASE1_HAMPERS.md) - same
in-memory-on-read-list-flushed-to-JSON pattern as stats.py.

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

ROOT = Path(__file__).resolve().parent.parent.parent
PROMOTED_ITEMS_PATH = Path(
    os.environ.get("PROMOTED_HAMPER_ITEMS_PATH", str(ROOT / ".cache" / "promoted_hamper_items.json"))
)

_LOCK = threading.Lock()


def _load() -> list[dict]:
    if PROMOTED_ITEMS_PATH.exists():
        try:
            data = json.loads(PROMOTED_ITEMS_PATH.read_text())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save(data: list[dict]) -> None:
    PROMOTED_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMOTED_ITEMS_PATH.write_text(json.dumps(data))


def get_promoted_items() -> list[HamperItem]:
    with _LOCK:
        rows = _load()
    return [
        HamperItem(
            name=row["name"],
            price=row["price"],
            category=row["category"],
            length_in=row.get("length_in"),
            breadth_in=row.get("breadth_in"),
            height_in=row.get("height_in"),
        )
        for row in rows
    ]


def is_name_taken(name: str, catalog_items: list[HamperItem]) -> bool:
    normalized = name.strip().lower()
    with _LOCK:
        promoted_names = {row["name"].strip().lower() for row in _load()}
    catalog_names = {item.name.strip().lower() for item in catalog_items}
    return normalized in promoted_names or normalized in catalog_names


def add_promoted_item(item: HamperCustomItem) -> None:
    with _LOCK:
        data = _load()
        data.append({
            "name": item.name,
            "price": item.price,
            "category": item.category,
            "length_in": item.length_in,
            "breadth_in": item.breadth_in,
            "height_in": item.height_in,
        })
        _save(data)
