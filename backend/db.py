"""Optional Postgres connection helper. Used only when DATABASE_URL is set
(a free Neon project - see promoted_products.py / hampers/promoted_items.py
for what actually gets stored there). Local dev without DATABASE_URL keeps
using the pre-existing file-backed JSON stores untouched.
"""

import os

DATABASE_URL = os.environ.get("DATABASE_URL")


def is_configured() -> bool:
    return bool(DATABASE_URL)


def get_connection():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)
