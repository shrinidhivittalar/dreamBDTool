from pathlib import Path

import pytest

from backend.hampers.catalog_loader import load_hamper_catalog

DATA_PATH = Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"


@pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")
def test_load_hamper_catalog_splits_containers_and_items():
    result = load_hamper_catalog(DATA_PATH)

    assert result.report.container_count > 0
    assert result.report.item_count > 0
    assert result.report.container_count + result.report.item_count + len(result.report.duplicate_names) \
        == result.report.row_count
    assert not result.report.skipped_rows

    container_names = {c.name for c in result.containers}
    assert "MDF Tray 16x10" in container_names

    item_names = {i.name for i in result.items}
    assert "Baked Mathri Hexagon 70g" in item_names


@pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")
def test_hamper_container_has_usable_volume():
    result = load_hamper_catalog(DATA_PATH)

    tray = next(c for c in result.containers if c.name == "MDF Tray 16x10")
    assert tray.usable_volume_in3 == pytest.approx(16.0 * 10.0 * 2.0)


def test_load_hamper_catalog_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_hamper_catalog(tmp_path / "missing.csv")


# --- Column-mapping regression tests -----------------------------------
#
# These pin down the exact bug found while testing category coverage: the
# sheet's "Category" column only distinguishes container vs item rows
# ("Hamper Box" / "Inside item"), it is NOT a real product category. The
# real category (Food / Merchandise / Gourmet item) lives in "Tag". If
# someone renames/reorders columns later, these should fail loudly instead
# of silently reverting to the old wrong-field bug.

CSV_HEADER = (
    "Items,Category,Price per unit,Rock Bottom,Vendor,Tag,"
    "Length (INCH),Breadth (INCH),Height (INCH),Primary Packaging,Secondary Packaging"
)


def _write_csv(tmp_path, rows: list[str]):
    path = tmp_path / "hampers.csv"
    path.write_text(CSV_HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_item_category_comes_from_tag_column_not_category_column(tmp_path):
    path = _write_csv(tmp_path, [
        "Sample Snack,Inside item,100,80,,Food,2,2,2,,",
        "Sample Candle,Inside Item,50,40,,Merchandise,1,1,1,,",
        "Sample Nuts,Inside item,200,160,,Gourmet item,2,2,2,,",
    ])

    result = load_hamper_catalog(path)

    categories = {item.name: item.category for item in result.items}
    assert categories == {
        "Sample Snack": "Food",
        "Sample Candle": "Merchandise",
        "Sample Nuts": "Gourmet item",
    }
    # None of the item categories should ever be the raw "Category" column
    # value - that would mean the bug has come back.
    assert "Inside item" not in categories.values()
    assert "Inside Item" not in categories.values()


def test_hamper_box_category_value_still_splits_container_from_items(tmp_path):
    path = _write_csv(tmp_path, [
        "Sample Box,Hamper Box,500,400,,Hamper,10,10,3,,",
        "Sample Snack,Inside item,100,80,,Food,2,2,2,,",
    ])

    result = load_hamper_catalog(path)

    assert [c.name for c in result.containers] == ["Sample Box"]
    assert [i.name for i in result.items] == ["Sample Snack"]


@pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")
def test_real_catalog_item_categories_are_real_product_categories():
    result = load_hamper_catalog(DATA_PATH)

    categories = {item.category for item in result.items if item.category}
    # Whatever the exact category set is, it must never collapse to the
    # container/item type marker - that's the specific bug this guards.
    assert "Inside item" not in categories
    assert "Inside Item" not in categories
    assert categories == {"Food", "Merchandise", "Gourmet item"}
