import pandas as pd

from backend.excel_loader import load_products


def _write_csv(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "catalog.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_rock_bottom_above_selling_price_is_nullified_not_dropped(tmp_path):
    path = _write_csv(tmp_path, [
        {"Product Name": "Brownie", "Selling Price": 80, "Rock Bottom Price": 90},
    ])
    products = load_products(path)
    assert len(products) == 1
    assert products[0].name == "Brownie"
    assert products[0].rock_bottom_price is None


def test_rock_bottom_below_selling_price_is_kept(tmp_path):
    path = _write_csv(tmp_path, [
        {"Product Name": "Brownie", "Selling Price": 100, "Rock Bottom Price": 90},
    ])
    products = load_products(path)
    assert products[0].rock_bottom_price == 90


def test_duplicate_names_keep_first_occurrence(tmp_path):
    path = _write_csv(tmp_path, [
        {"Product Name": "Brownie", "Selling Price": 100, "Vendor": "First Vendor"},
        {"Product Name": "Brownie", "Selling Price": 120, "Vendor": "Second Vendor"},
    ])
    products = load_products(path)
    assert len(products) == 1
    assert products[0].vendor == "First Vendor"
    assert products[0].selling_price == 100


def test_duplicate_names_case_insensitive(tmp_path):
    path = _write_csv(tmp_path, [
        {"Product Name": "Brownie", "Selling Price": 100},
        {"Product Name": "brownie", "Selling Price": 120},
    ])
    products = load_products(path)
    assert len(products) == 1


def test_row_that_fails_to_load_does_not_block_a_later_valid_duplicate(tmp_path):
    path = _write_csv(tmp_path, [
        {"Product Name": "Brownie", "Selling Price": -5},
        {"Product Name": "Brownie", "Selling Price": 100},
    ])
    products = load_products(path)
    assert len(products) == 1
    assert products[0].selling_price == 100


def test_empty_catalog_returns_empty_list(tmp_path):
    path = _write_csv(tmp_path, [
        {"Product Name": "", "Selling Price": ""},
    ])
    assert load_products(path) == []
