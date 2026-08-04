import pytest
import pandas as pd

from backend.data_provider import ProductDataProvider


def _xlsx_bytes(tmp_path, rows: list[dict]) -> bytes:
    pytest.importorskip("openpyxl")
    path = tmp_path / "catalog.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False)
    return path.read_bytes()


class FakeProvider(ProductDataProvider):
    def __init__(self, payload: bytes | Exception, cache_path):
        super().__init__(source_url="https://example.test/catalog.xlsx", cache_path=cache_path)
        self.payload = payload

    def _download_latest(self) -> bytes:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_refresh_downloads_parses_and_caches_products(tmp_path):
    payload = _xlsx_bytes(tmp_path, [
        {"Product Name": "Brownie", "Selling Price": 100, "Rock Bottom Price": 90, "Category": "In-house sweet"},
    ])
    provider = FakeProvider(payload, tmp_path / "cache.xlsx")

    status = provider.refresh()

    assert status.product_count == 1
    assert status.last_error is None
    assert provider.get_products()[0].name == "Brownie"
    assert (tmp_path / "cache.xlsx").exists()


def test_refresh_failure_uses_cached_products(tmp_path):
    cache_path = tmp_path / "cache.xlsx"
    cache_path.write_bytes(_xlsx_bytes(tmp_path, [
        {"Product Name": "Cached Brownie", "Selling Price": 100, "Category": "In-house sweet"},
    ]))
    provider = FakeProvider(RuntimeError("Zoho unavailable"), cache_path)

    status = provider.refresh()

    assert status.product_count == 1
    assert status.using_cache is True
    assert status.warning
    assert provider.get_products()[0].name == "Cached Brownie"


def test_refresh_failure_without_cache_is_non_blocking(tmp_path):
    provider = FakeProvider(RuntimeError("Zoho unavailable"), tmp_path / "missing-cache.xlsx")

    status = provider.refresh()

    assert status.product_count == 0
    assert status.warning
    assert provider.get_products() == []



def test_initial_load_uses_local_file(tmp_path):
    local = tmp_path / "local.csv"
    pd.DataFrame([
        {"Product Name": "Local Brownie", "Selling Price": 100},
    ]).to_csv(local, index=False)
    provider = ProductDataProvider(cache_path=tmp_path / "cache.xlsx", local_catalog_path=local)

    status = provider.load_initial()

    assert status.product_count == 1
    assert provider.get_products()[0].name == "Local Brownie"
    assert status.current_source == str(local)


def test_refresh_from_uploaded_csv_bytes_parses_and_caches(tmp_path):
    payload = b"Product Name,Selling Price\nUploaded Brownie,100\n"
    cache_path = tmp_path / "cache"
    provider = ProductDataProvider(cache_path=cache_path)

    status = provider.refresh_from_bytes(payload, filename="upload.csv")

    assert status.product_count == 1
    assert provider.get_products()[0].name == "Uploaded Brownie"
    assert cache_path.with_suffix(".csv").exists()


def test_validation_warnings_surface_for_bad_rows_and_duplicates(tmp_path):
    payload = b"Product Name,Selling Price\n,100\nBrownie,100\nBrownie,120\nBad Price,nope\n"
    provider = ProductDataProvider(cache_path=tmp_path / "cache.csv")

    status = provider.refresh_from_bytes(payload, filename="upload.csv", cache=False)

    assert status.product_count == 1
    assert status.validation_warnings
