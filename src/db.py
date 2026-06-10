"""
db.py  --  shared helper for opening the MinimAIze database.

Every phase from here on needs to read minimaize.db. Instead of repeating the
connection code in each file, we write it once here and `import db` elsewhere.
"""

import sqlite3
from pathlib import Path

# Same location the generator writes to: <project>/data/minimaize.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "minimaize.db"


def connect():
    """Open the database and return a connection.

    Raises a friendly error if the database hasn't been generated yet."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}.\n"
            f"Run 'py src\\generate_data.py' first to create it."
        )
    conn = sqlite3.connect(DB_PATH)
    # row_factory = sqlite3.Row lets us read columns by NAME (row["product_name"])
    # instead of by numeric position (row[1]) -- far easier to read.
    conn.row_factory = sqlite3.Row
    return conn
