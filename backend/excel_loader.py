try:
    from .catalog_loader import COLUMN_ALIASES, load_catalog, load_catalog_bytes, load_products
except ImportError:
    from catalog_loader import COLUMN_ALIASES, load_catalog, load_catalog_bytes, load_products
