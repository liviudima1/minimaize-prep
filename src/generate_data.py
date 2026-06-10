"""
generate_data.py  --  Phase 1 of MinimAIze
===========================================

Builds a FAKE "data warehouse" full of synthetic METADATA.

In the real world, Snowflake and Databricks expose system tables describing every
table (its size, when it was created) and a log of every query run against them
(who ran it, when, was it a read or a write). We don't have those platforms on a
laptop, so this script invents believable versions of that metadata and saves it
into a local SQLite database file: data/minimaize.db

Nothing here is "real" data -- there are no actual customer/claims rows, only
FACTS ABOUT tables (names, sizes, usage). That mirrors MinimAIze's metadata-only rule.

Run it with:   py src\\generate_data.py
"""

import sqlite3                       # SQLite database engine -- built into Python, no install needed
import random                        # to invent believable random numbers
from datetime import datetime, timedelta
from pathlib import Path             # a modern, OS-safe way to build file paths

# random.seed makes the "random" data identical on every run, so your results are
# stable while you learn. Remove this line later if you want fresh data each time.
random.seed(42)

# A fixed "today" for the simulation. Anchoring to one date keeps numbers like
# "no reads in 412 days" consistent every run.
TODAY = datetime(2026, 6, 10)

# Build the path to data/minimaize.db relative to THIS file, so it works no matter
# what folder you run the script from.  __file__ is this script's own location.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "minimaize.db"


# ---------------------------------------------------------------------------
# 1. The catalog of products we'll invent.
#    Each entry is (product name, business domain, "profile").
#    The profile is a label WE use to decide how alive or wasteful the product
#    looks -- it is NOT stored in the database (the real system has to figure
#    that out from usage; we're just using it as a recipe).
# ---------------------------------------------------------------------------
PRODUCTS = [
    ("Member 360 Product",          "Membership", "healthy"),
    ("Claims Real-Time Product",    "Claims",     "healthy"),
    ("Provider Network Product",    "Provider",   "healthy"),
    ("Pharmacy Insights Product",   "Pharmacy",   "healthy"),
    ("Care Management Product",     "Clinical",   "monitor"),
    ("Risk Scoring Product",        "Actuarial",  "monitor"),
    ("Marketing Engagement Product","Marketing",  "monitor"),
    ("Finance Reporting Product",   "Finance",    "review"),
    ("Quality Measures Product",    "Quality",    "review"),
    ("Legacy Provider Archive",     "Provider",   "dead"),
    ("Claims Historical Product",   "Claims",     "dead"),
    ("Pharmacy Analytics Archive",  "Pharmacy",   "dead"),
]

# For each profile, the "knobs" that shape its data. A dict (like a Java HashMap)
# mapping the profile name to a tuple of ranges:
#   (assets count, size in GB, days since last query, distinct consumers, total queries)
PROFILE_RULES = {
    #              n_assets   size_gb         days_idle    consumers   total_queries
    "healthy":  ((4, 8),    (5, 500),       (0, 7),      (8, 40),    (800, 3000)),
    "monitor":  ((3, 6),    (5, 800),       (10, 60),    (3, 10),    (100, 600)),
    "review":   ((2, 5),    (10, 2000),     (60, 150),   (1, 4),     (10, 80)),
    "dead":     ((2, 6),    (50, 130000),   (200, 500),  (0, 2),     (0, 25)),
}

# A pool of fake users who run queries. f"..." is an f-string: Python's way of
# slotting variables into text. {i:02d} means "the number i, padded to 2 digits".
USERS = [f"user{i:02d}@company.com" for i in range(1, 61)]

# A few realistic schema/table name fragments to assemble asset names from.
SCHEMAS = ["raw", "curated", "analytics", "reporting", "archive"]
TABLE_WORDS = ["fact", "dim", "summary", "history", "snapshot", "detail", "agg"]
PLATFORMS = ["Snowflake", "Databricks"]
OBJECT_TYPES = ["TABLE", "TABLE", "TABLE", "EXTERNAL TABLE", "VOLUME"]  # weighted toward TABLE

# --- Reference data for the two extra sources: EDC (catalog) and AskID (ownership) ---
FIRST_NAMES = ["James", "Maria", "David", "Linda", "Robert", "Emily",
               "Michael", "Sarah", "Daniel", "Anna", "Kevin", "Priya"]
LAST_NAMES = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Martin",
              "Davis", "Lopez", "Wilson", "Clark", "Nguyen", "Patel"]
CLASSIFICATIONS = ["Public", "Internal", "Confidential", "Restricted"]
# Each business domain rolls up to ONE cio -- this lets us later total cost "by CIO".
DOMAIN_CIO = {
    "Membership": "Patricia Gomez", "Clinical": "Patricia Gomez", "Quality": "Patricia Gomez",
    "Claims": "Raj Patel",          "Provider": "Raj Patel",      "Pharmacy": "Raj Patel",
    "Actuarial": "Susan Clark",     "Marketing": "Susan Clark",   "Finance": "Susan Clark",
}
# Healthy products tend to be more business-critical; dead ones less so.
CRITICALITY_BY_PROFILE = {
    "healthy": ["High", "Critical"], "monitor": ["Medium", "High"],
    "review":  ["Low", "Medium"],    "dead":    ["Low", "Medium"],
}
# Deliberate governance GAPS -- MinimAIze must detect and flag these.
PRODUCTS_WITHOUT_OWNERSHIP = {"Legacy Provider Archive"}
PRODUCTS_WITHOUT_CATALOG = {"Claims Historical Product"}


def create_tables(cur):
    """Create the three empty tables. Triple-quoted strings let SQL span lines."""
    cur.execute("""
        CREATE TABLE data_products (
            product_id   INTEGER PRIMARY KEY,
            product_name TEXT,
            domain       TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE assets (
            asset_id          INTEGER PRIMARY KEY,
            product_id        INTEGER,          -- which product this asset belongs to
            platform          TEXT,             -- Snowflake or Databricks
            database_name     TEXT,
            schema_name       TEXT,
            table_name        TEXT,
            object_type       TEXT,             -- TABLE, EXTERNAL TABLE, VOLUME
            size_bytes        INTEGER,          -- how big it is on disk
            row_count         INTEGER,
            created_date      TEXT,             -- ISO date string, e.g. '2021-03-14'
            last_altered_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE query_history (
            query_id        INTEGER PRIMARY KEY,
            asset_id        INTEGER,            -- which asset was touched
            user_name       TEXT,               -- who ran the query (a "consumer")
            query_type      TEXT,               -- 'READ' or 'WRITE'
            query_timestamp TEXT                -- when it ran
        )
    """)
    # EDC = Enterprise Data Catalog: business metadata about each product.
    cur.execute("""
        CREATE TABLE edc_catalog (
            product_id     INTEGER PRIMARY KEY,
            description    TEXT,
            classification TEXT,                -- Public / Internal / Confidential / Restricted
            criticality    TEXT,                -- Low / Medium / High / Critical
            steward        TEXT
        )
    """)
    # AskID = the ownership directory: who is accountable, up the management chain.
    cur.execute("""
        CREATE TABLE askid_ownership (
            product_id    INTEGER PRIMARY KEY,
            product_owner TEXT,
            director      TEXT,
            vp            TEXT,
            cio           TEXT
        )
    """)


def random_date(start_days_ago, end_days_ago):
    """Return an ISO date string between start/end days before TODAY.
    Example: random_date(1825, 365) = somewhere between 5 years and 1 year ago."""
    span = start_days_ago - end_days_ago
    offset = end_days_ago + random.randint(0, max(span, 0))
    return (TODAY - timedelta(days=offset)).strftime("%Y-%m-%d")


def random_person():
    """Make up a 'First Last' name."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate():
    # Make sure the data/ folder exists, then start the DB fresh each run.
    DB_PATH.parent.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()  # delete the old file so we rebuild cleanly

    conn = sqlite3.connect(DB_PATH)   # opens (creates) the database file
    cur = conn.cursor()               # a cursor is the handle you run SQL through
    create_tables(cur)

    asset_id = 1
    query_id = 1
    asset_rows = []
    query_rows = []
    edc_rows = []
    askid_rows = []

    # enumerate(..., start=1) gives us (index, item) pairs -- handy for IDs.
    for product_id, (name, domain, profile) in enumerate(PRODUCTS, start=1):
        cur.execute(
            "INSERT INTO data_products VALUES (?, ?, ?)",
            (product_id, name, domain),
        )

        # EDC catalog entry -- skipped for products with a deliberate metadata gap.
        if name not in PRODUCTS_WITHOUT_CATALOG:
            edc_rows.append((
                product_id,
                f"{name} -- curated {domain.lower()} data for analytics and reporting.",
                random.choice(CLASSIFICATIONS),
                random.choice(CRITICALITY_BY_PROFILE[profile]),
                random_person(),                       # steward
            ))
        # AskID ownership chain -- skipped for products with a deliberate ownership gap.
        if name not in PRODUCTS_WITHOUT_OWNERSHIP:
            askid_rows.append((
                product_id,
                random_person(),                        # product owner
                random_person(),                        # director
                random_person(),                        # vp
                DOMAIN_CIO[domain],                     # cio
            ))

        # Unpack this profile's knobs. The * unpacks a tuple into randint's two args.
        n_assets_rng, size_rng, idle_rng, consumers_rng, queries_rng = PROFILE_RULES[profile]
        n_assets = random.randint(*n_assets_rng)

        # Pick this product's set of consumers (may be empty for dead products).
        n_consumers = random.randint(*consumers_rng)
        consumers = random.sample(USERS, n_consumers) if n_consumers > 0 else []

        # How many days ago was this product last touched, and how many queries total.
        days_idle = random.randint(*idle_rng)
        last_activity = TODAY - timedelta(days=days_idle)
        total_queries = random.randint(*queries_rng)

        # --- create this product's assets ---
        product_asset_ids = []
        for _ in range(n_assets):
            size_gb = random.randint(*size_rng)
            size_bytes = size_gb * (1024 ** 3)               # GB -> bytes
            created = random_date(2000, 200)                 # created 6mo to ~5.5yr ago
            table_name = f"{random.choice(TABLE_WORDS)}_{random.choice(TABLE_WORDS)}_{asset_id}"

            asset_rows.append((
                asset_id,
                product_id,
                random.choice(PLATFORMS),
                f"{domain.upper()}_DB",
                random.choice(SCHEMAS),
                table_name,
                random.choice(OBJECT_TYPES),
                size_bytes,
                size_gb * random.randint(1000, 5000),        # fake row_count
                created,
                random_date(199, days_idle),                 # last altered after creation
            ))
            product_asset_ids.append(asset_id)
            asset_id += 1

        # --- create this product's query history ---
        # Spread queries over the ~12 months ending at last_activity.
        for q in range(total_queries):
            # The very first query we force to land exactly on last_activity, so the
            # product's "last read" date matches days_idle precisely.
            if q == 0:
                ts = last_activity
            else:
                ts = last_activity - timedelta(days=random.randint(0, 365))
            # 85% reads, 15% writes -- reads are far more common than writes.
            qtype = "READ" if random.random() < 0.85 else "WRITE"
            user = random.choice(consumers) if consumers else "etl_service@company.com"

            query_rows.append((
                query_id,
                random.choice(product_asset_ids),
                user,
                qtype,
                ts.strftime("%Y-%m-%d"),
            ))
            query_id += 1

    # executemany inserts all rows in one efficient batch. The "?" are placeholders
    # Python safely fills in -- never build SQL by gluing strings together.
    cur.executemany(
        "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", asset_rows
    )
    cur.executemany(
        "INSERT INTO query_history VALUES (?, ?, ?, ?, ?)", query_rows
    )
    cur.executemany(
        "INSERT INTO edc_catalog VALUES (?, ?, ?, ?, ?)", edc_rows
    )
    cur.executemany(
        "INSERT INTO askid_ownership VALUES (?, ?, ?, ?, ?)", askid_rows
    )

    conn.commit()   # SAVE everything to the file (nothing is permanent until commit)
    summarize(cur)
    conn.close()


def summarize(cur):
    """Print a quick report using SQL aggregate queries -- a gentle SQL warm-up."""
    print(f"\nDatabase created at: {DB_PATH}\n")

    cur.execute("SELECT COUNT(*) FROM data_products")
    print(f"  Data products : {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*), SUM(size_bytes) FROM assets")
    n_assets, total_bytes = cur.fetchone()
    print(f"  Assets        : {n_assets}")
    print(f"  Total storage : {total_bytes / (1024**4):,.1f} TB")
    cur.execute("SELECT COUNT(*) FROM query_history")
    print(f"  Query events  : {cur.fetchone()[0]}")

    print("\n  Per-product snapshot (most recently used first):")
    print(f"  {'Product':<30}{'Domain':<12}{'Assets':>7}{'Size(TB)':>10}{'Last read':>13}")
    # Each value comes from its OWN sub-query, so joining one table to another can't
    # multiply (fan out) the numbers. A sub-query in SELECT runs once per product row.
    cur.execute("""
        SELECT  p.product_name,
                p.domain,
                (SELECT COUNT(*)        FROM assets a WHERE a.product_id = p.product_id) AS assets,
                (SELECT SUM(size_bytes) FROM assets a WHERE a.product_id = p.product_id) AS bytes,
                (SELECT MAX(q.query_timestamp)
                   FROM query_history q
                   JOIN assets a ON a.asset_id = q.asset_id
                  WHERE a.product_id = p.product_id AND q.query_type = 'READ') AS last_read
        FROM data_products p
        ORDER BY last_read DESC
    """)
    for name, domain, assets, byts, last_read in cur.fetchall():
        tb = (byts or 0) / (1024 ** 4)
        print(f"  {name:<30}{domain:<12}{assets:>7}{tb:>10.1f}{str(last_read):>13}")


# This guard means "only run generate() when the file is executed directly,
# not when it's imported by another script." A common Python idiom.
if __name__ == "__main__":
    generate()
