from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .models import Product
except ImportError:
    from models import Product


COLUMN_ALIASES = {
    "name": ["Product Name", "Better for you Options", "Product"],
    "selling_price": ["Selling Price", "DaD Selling price", "DaD Selling Price"],
    "rock_bottom_price": ["Rock Bottom Price", "Rock bottom"],
    "category": ["Category", "Tag"],
    "vendor": ["Vendor"],
    "tags": ["Tags", "Tag"],
    "sourcing": ["In-house / Outsourced", "Sourcing"],
}


def _find_column(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def _text(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def load_products(path: str | Path) -> list[Product]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Product catalog not found: {source}")

    frame = pd.read_csv(source) if source.suffix.lower() == ".csv" else pd.read_excel(source)
    name_column = _find_column(frame, COLUMN_ALIASES["name"])
    price_column = _find_column(frame, COLUMN_ALIASES["selling_price"])
    if not name_column or not price_column:
        raise ValueError("Catalog must contain a product name and selling price column")

    columns = {key: _find_column(frame, aliases) for key, aliases in COLUMN_ALIASES.items()}
    products: list[Product] = []
    seen_names: set[str] = set()
    for _, row in frame.iterrows():
        name = _text(row[name_column])
        if not name:
            continue
        needle = name.lower()
        if needle in seen_names:
            continue
        try:
            price = float(row[price_column])
        except (TypeError, ValueError):
            continue
        if price < 0:
            continue
        tags_value = _text(row[columns["tags"]]) if columns["tags"] else ""
        tags = [tag.strip() for tag in tags_value.replace(";", ",").split(",") if tag.strip()]
        if not tags and columns["category"]:
            tags = [tag.strip() for tag in _text(row[columns["category"]]).split("-") if tag.strip()]
        rock_bottom = None
        if columns["rock_bottom_price"]:
            try:
                rock_bottom = float(row[columns["rock_bottom_price"]])
            except (TypeError, ValueError):
                pass
            # Rock Bottom Price isn't used by the recommender yet (reserved
            # for a future negotiation feature), so a bad value shouldn't
            # drop an otherwise-valid, actively-used product — just treat
            # it as unknown, the same way an unparseable value already is.
            if rock_bottom is not None and rock_bottom > price:
                rock_bottom = None
        seen_names.add(needle)
        products.append(Product(
            name=name,
            selling_price=price,
            rock_bottom_price=rock_bottom,
            category=_text(row[columns["category"]]) if columns["category"] else "",
            vendor=_text(row[columns["vendor"]]) if columns["vendor"] else "",
            tags=tags,
            sourcing=_text(row[columns["sourcing"]]) if columns["sourcing"] else "",
        ))
    return products



