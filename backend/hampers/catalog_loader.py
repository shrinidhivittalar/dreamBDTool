import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .models import HamperContainer, HamperItem
except ImportError:
    from models import HamperContainer, HamperItem


# The hamper catalog sheet is a single table with both container rows
# ("Hamper Box") and item rows ("Inside item"/"Inside Item") mixed together,
# distinguished by the Category column - unlike the snack-box catalog, which
# is one product per row with no container concept.
CONTAINER_CATEGORY_VALUES = {"hamper box"}

COLUMN_ALIASES = {
    "name": ["Items", "Item"],
    "price": ["Price per unit", "Price"],
    "rock_bottom_price": ["Rock Bottom", "Rock bottom"],
    "category": ["Category"],
    "vendor": ["Vendor"],
    "tags": ["Tag", "Tags"],
    "length_in": ["Length (INCH)", "Length"],
    "breadth_in": ["Breadth (INCH)", "Breadth"],
    "height_in": ["Height (INCH)", "Height"],
    "primary_packaging": ["Primary Packaging"],
    "secondary_packaging": ["Secondary Packaging"],
    "upright_only": ["Upright Only", "Must Stay Upright", "Orientation"],
}

TRUE_VALUES = {"y", "yes", "true", "1", "upright", "upright only"}


@dataclass(frozen=True)
class HamperCatalogValidationReport:
    source_name: str
    row_count: int
    container_count: int
    item_count: int
    skipped_rows: list[str] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.skipped_rows:
            warnings.append(f"Skipped {len(self.skipped_rows)} invalid row(s).")
        if self.duplicate_names:
            warnings.append(f"Ignored {len(self.duplicate_names)} duplicate name(s).")
        return warnings


@dataclass(frozen=True)
class HamperCatalogLoadResult:
    containers: list[HamperContainer]
    items: list[HamperItem]
    report: HamperCatalogValidationReport
    # Container names that have a dedicated per-container eligibility
    # column in the source sheet (2026-09-03 "which containers can this
    # item go in" columns) - a container NOT in this set has no eligibility
    # data at all (e.g. the sheet gap for "10 x 10 x 3 w cavity - Jaipur
    # palace"), so recommend_hampers() must skip the eligibility filter for
    # it entirely rather than treat every item as excluded there.
    eligible_container_names: frozenset[str] = field(default_factory=frozenset)


def _find_column(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def _text(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _number(value: Any) -> float | None:
    if pd.isna(value) or _text(value) == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_frame(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(source)
    raise ValueError(f"Unsupported hamper catalog file type: {source.suffix or 'unknown'}")


def load_hamper_catalog(path: str | Path, source_name: str | None = None) -> HamperCatalogLoadResult:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Hamper catalog not found: {source}")

    frame = _read_frame(source)
    name_column = _find_column(frame, COLUMN_ALIASES["name"])
    price_column = _find_column(frame, COLUMN_ALIASES["price"])
    category_column = _find_column(frame, COLUMN_ALIASES["category"])
    if not name_column or not price_column:
        raise ValueError("Hamper catalog must contain an item name and price column")

    columns = {key: _find_column(frame, aliases) for key, aliases in COLUMN_ALIASES.items()}

    # Per-container eligibility columns (2026-09-03): any column that isn't
    # one of the recognized fields above and isn't blank/pandas'
    # auto-generated "Unnamed: N" for a genuinely empty header. Their header
    # text IS the container's name, by the sheet's own design - the same
    # string that appears in the Items column for that container's row.
    known_columns = {name_column, category_column} | {v for v in columns.values() if v}
    eligibility_columns = [
        column for column in frame.columns
        if column not in known_columns
        and str(column).strip() != ""
        and not str(column).strip().lower().startswith("unnamed")
    ]

    containers: list[HamperContainer] = []
    items: list[HamperItem] = []
    skipped_rows: list[str] = []
    duplicate_names: list[str] = []
    seen_names: set[str] = set()

    for index, row in frame.iterrows():
        row_number = int(index) + 2
        name = _text(row[name_column])
        if not name:
            skipped_rows.append(f"Row {row_number}: missing item name")
            continue
        needle = name.lower()
        if needle in seen_names:
            duplicate_names.append(name)
            continue

        price = _number(row[price_column])
        if price is None:
            skipped_rows.append(f"Row {row_number}: invalid price for {name}")
            continue
        if price < 0:
            skipped_rows.append(f"Row {row_number}: negative price for {name}")
            continue

        rock_bottom = _number(row[columns["rock_bottom_price"]]) if columns["rock_bottom_price"] else None
        if rock_bottom is not None and rock_bottom > price:
            rock_bottom = None

        category_text = _text(row[category_column]) if category_column else ""
        vendor = _text(row[columns["vendor"]]) if columns["vendor"] else ""
        tags_value = _text(row[columns["tags"]]) if columns["tags"] else ""
        tags = [tag.strip() for tag in tags_value.replace(";", ",").split(",") if tag.strip()]
        length_in = _number(row[columns["length_in"]]) if columns["length_in"] else None
        breadth_in = _number(row[columns["breadth_in"]]) if columns["breadth_in"] else None
        height_in = _number(row[columns["height_in"]]) if columns["height_in"] else None

        seen_names.add(needle)

        if category_text.strip().lower() in CONTAINER_CATEGORY_VALUES:
            containers.append(HamperContainer(
                name=name,
                price=price,
                rock_bottom_price=rock_bottom,
                length_in=length_in,
                breadth_in=breadth_in,
                height_in=height_in,
                vendor=vendor,
                tags=tags,
            ))
        else:
            primary_packaging = _text(row[columns["primary_packaging"]]) if columns["primary_packaging"] else ""
            secondary_packaging = _text(row[columns["secondary_packaging"]]) if columns["secondary_packaging"] else ""
            upright_only = (
                _text(row[columns["upright_only"]]).strip().lower() in TRUE_VALUES
                if columns["upright_only"] else False
            )
            if eligibility_columns:
                eligibility_values = {column: _text(row[column]).strip().lower() for column in eligibility_columns}
                has_any_eligibility_data = any(value != "" for value in eligibility_values.values())
                allowed_containers = (
                    frozenset(column for column, value in eligibility_values.items() if value in TRUE_VALUES)
                    if has_any_eligibility_data else None
                )
            else:
                allowed_containers = None
            # The sheet's "Category" column only distinguishes container vs
            # item rows ("Hamper Box" / "Inside item") - it's not a real
            # product category. The actual category (Food / Merchandise /
            # Gourmet item) lives in the "Tag" column, so that's what an
            # item's category is set from.
            items.append(HamperItem(
                name=name,
                price=price,
                rock_bottom_price=rock_bottom,
                category=tags[0] if tags else category_text,
                vendor=vendor,
                tags=tags,
                length_in=length_in,
                breadth_in=breadth_in,
                height_in=height_in,
                primary_packaging=primary_packaging,
                secondary_packaging=secondary_packaging,
                upright_only=upright_only,
                allowed_containers=allowed_containers,
            ))

    report = HamperCatalogValidationReport(
        source_name=source_name or source.name,
        row_count=len(frame.index),
        container_count=len(containers),
        item_count=len(items),
        skipped_rows=skipped_rows,
        duplicate_names=duplicate_names,
    )
    return HamperCatalogLoadResult(
        containers=containers,
        items=items,
        report=report,
        eligible_container_names=frozenset(str(column) for column in eligibility_columns),
    )


def load_hamper_catalog_bytes(payload: bytes, filename: str = "hampers.csv") -> HamperCatalogLoadResult:
    suffix = Path(filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as file:
        file.write(payload)
        temp_path = Path(file.name)
    try:
        return load_hamper_catalog(temp_path, source_name=filename)
    finally:
        temp_path.unlink(missing_ok=True)
