import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .models import Product
    from .recommender_config import CUSTOMIZATION_ELIGIBLE_PRODUCT_NAMES, THEMED_CUSTOMISED_CATEGORY_MARKERS
except ImportError:
    from models import Product
    from recommender_config import CUSTOMIZATION_ELIGIBLE_PRODUCT_NAMES, THEMED_CUSTOMISED_CATEGORY_MARKERS


COLUMN_ALIASES = {
    "name": ["Product Name", "Better for you Options", "Product"],
    "selling_price": ["Selling Price", "DaD Selling price", "DaD Selling Price"],
    "rock_bottom_price": ["Rock Bottom Price", "Rock bottom"],
    "category": ["Category", "Tag"],
    "vendor": ["Vendor"],
    "tags": ["Tags", "Tag"],
    "sourcing": ["In-house / Outsourced", "Sourcing"],
    # The source sheet leaves these two columns unheadered - pandas names
    # them positionally ("Unnamed: 5"/"Unnamed: 6"). Named aliases are kept
    # first so a future sheet with real headers is picked up automatically.
    "packaging_note": ["Packaging", "Packaging Note", "Unnamed: 5"],
    "packaging_addon_cost": ["Packaging Cost", "Add-on Cost", "Unnamed: 6"],
}


def _normalized_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


@dataclass(frozen=True)
class CatalogValidationReport:
    source_name: str
    row_count: int
    product_count: int
    skipped_rows: list[str] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.skipped_rows:
            warnings.append(f"Skipped {len(self.skipped_rows)} invalid row(s).")
        if self.duplicate_names:
            warnings.append(f"Ignored {len(self.duplicate_names)} duplicate product name(s).")
        return warnings


@dataclass(frozen=True)
class CatalogLoadResult:
    products: list[Product]
    report: CatalogValidationReport


def _find_column(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def _text(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _read_frame(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(source)
    raise ValueError(f"Unsupported catalog file type: {source.suffix or 'unknown'}")


def load_catalog(path: str | Path, source_name: str | None = None) -> CatalogLoadResult:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Product catalog not found: {source}")

    frame = _read_frame(source)
    name_column = _find_column(frame, COLUMN_ALIASES["name"])
    price_column = _find_column(frame, COLUMN_ALIASES["selling_price"])
    if not name_column or not price_column:
        raise ValueError("Catalog must contain a product name and selling price column")

    columns = {key: _find_column(frame, aliases) for key, aliases in COLUMN_ALIASES.items()}
    products: list[Product] = []
    skipped_rows: list[str] = []
    duplicate_names: list[str] = []
    seen_names: set[str] = set()

    for index, row in frame.iterrows():
        row_number = int(index) + 2
        name = _text(row[name_column])
        if not name:
            skipped_rows.append(f"Row {row_number}: missing product name")
            continue
        needle = name.lower()
        if needle in seen_names:
            duplicate_names.append(name)
            continue
        try:
            price = float(row[price_column])
        except (TypeError, ValueError):
            skipped_rows.append(f"Row {row_number}: invalid selling price for {name}")
            continue
        if price < 0:
            skipped_rows.append(f"Row {row_number}: negative selling price for {name}")
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
            if rock_bottom is not None and rock_bottom > price:
                rock_bottom = None

        packaging_note = _text(row[columns["packaging_note"]]) if columns["packaging_note"] else ""
        packaging_addon_cost = None
        if columns["packaging_addon_cost"] and not pd.isna(row[columns["packaging_addon_cost"]]):
            try:
                packaging_addon_cost = float(row[columns["packaging_addon_cost"]])
            except (TypeError, ValueError):
                pass

        category_text = _text(row[columns["category"]]) if columns["category"] else ""
        is_customization_addon = any(
            marker in _normalized_name(category_text) or any(marker in tag.lower() for tag in tags)
            for marker in THEMED_CUSTOMISED_CATEGORY_MARKERS
        )
        customization_eligible = _normalized_name(name) in CUSTOMIZATION_ELIGIBLE_PRODUCT_NAMES

        seen_names.add(needle)
        products.append(Product(
            name=name,
            selling_price=price,
            rock_bottom_price=rock_bottom,
            category=category_text,
            vendor=_text(row[columns["vendor"]]) if columns["vendor"] else "",
            tags=tags,
            sourcing=_text(row[columns["sourcing"]]) if columns["sourcing"] else "",
            packaging_note=packaging_note,
            packaging_addon_cost=packaging_addon_cost,
            customization_eligible=customization_eligible,
            is_customization_addon=is_customization_addon,
        ))

    report = CatalogValidationReport(
        source_name=source_name or source.name,
        row_count=len(frame.index),
        product_count=len(products),
        skipped_rows=skipped_rows,
        duplicate_names=duplicate_names,
    )
    return CatalogLoadResult(products=products, report=report)


def load_products(path: str | Path) -> list[Product]:
    return load_catalog(path).products


def load_catalog_bytes(payload: bytes, filename: str = "catalog.xlsx") -> CatalogLoadResult:
    suffix = Path(filename).suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as file:
        file.write(payload)
        temp_path = Path(file.name)
    try:
        return load_catalog(temp_path, source_name=filename)
    finally:
        temp_path.unlink(missing_ok=True)
