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
