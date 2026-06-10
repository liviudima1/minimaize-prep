"""
inventory.py  --  Phase 2 of MinimAIze
=======================================

Builds the unified PRODUCT inventory (FR-1) and ASSET inventory (FR-2) by joining
the warehouse metadata with the EDC catalog and AskID ownership sources.

Design note: each function RETURNS data (so later phases can reuse it), and the
printing lives separately at the bottom. Keep "get the data" and "show the data"
apart -- it makes code far easier to reuse.

Run it with:   py src\\inventory.py
"""

import db   # our own src/db.py helper from Move 2


def get_product_inventory():
    """Return one row per product, enriched with owner (AskID) + catalog (EDC).

    LEFT JOIN keeps every product even if its ownership/catalog row is missing;
    those columns simply come back as None (Python's version of 'no value')."""
    conn = db.connect()
    rows = conn.execute("""
        SELECT  p.product_id,
                p.product_name,
                p.domain,
                o.product_owner,
                o.cio,
                e.steward,
                e.description,
                e.classification,
                e.criticality
        FROM data_products p
        LEFT JOIN askid_ownership o ON o.product_id = p.product_id
        LEFT JOIN edc_catalog     e ON e.product_id = p.product_id
        ORDER BY p.product_name
    """).fetchall()
    conn.close()
    return rows


def get_asset_inventory(product_id=None):
    """Return assets (FR-2), newest-largest first. Optionally filter to one product.

    The `product_id=None` default means the argument is optional -- call it with
    no arguments for ALL assets, or pass an id to get just one product's assets."""
    conn = db.connect()
    sql = """
        SELECT  a.asset_id,
                p.product_name,
                a.platform,
                a.database_name,
                a.schema_name,
                a.table_name,
                a.object_type,
                a.size_bytes,
                a.created_date
        FROM assets a
        LEFT JOIN data_products p ON p.product_id = a.product_id
    """
    params = ()
    if product_id is not None:
        sql += " WHERE a.product_id = ?"
        params = (product_id,)
    sql += " ORDER BY a.size_bytes DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def print_inventories():
    products = get_product_inventory()

    print(f"\nPRODUCT INVENTORY  ({len(products)} products)\n")
    print(f"  {'Product':<30}{'Owner':<17}{'CIO':<17}{'Class':<14}{'Crit':<9}")
    print(f"  {'-' * 84}")
    for r in products:
        # `value or fallback` uses Python truthiness: None (a missing value) is
        # 'falsy', so we substitute a clear marker instead of printing 'None'.
        owner = r["product_owner"] or ">> MISSING <<"
        cio = r["cio"] or ">> MISSING <<"
        clas = r["classification"] or "-"
        crit = r["criticality"] or "-"
        print(f"  {r['product_name']:<30}{owner:<17}{cio:<17}{clas:<14}{crit:<9}")

    # Governance gaps -- a list comprehension: "the name of each product whose
    # owner/description is missing". Concise Python idiom for filter+collect.
    no_owner = [r["product_name"] for r in products if not r["product_owner"]]
    no_meta = [r["product_name"] for r in products if not r["description"]]
    print("\n  GOVERNANCE GAPS")
    print(f"    Lacking ownership : {', '.join(no_owner) if no_owner else 'none'}")
    print(f"    Lacking metadata  : {', '.join(no_meta) if no_meta else 'none'}")

    assets = get_asset_inventory()
    print(f"\nASSET INVENTORY  ({len(assets)} assets)   --   10 largest:\n")
    print(f"  {'Table':<22}{'Product':<28}{'Platform':<12}{'Size (TB)':>10}")
    print(f"  {'-' * 72}")
    for a in assets[:10]:
        tb = a["size_bytes"] / (1024 ** 4)
        product = a["product_name"] or "(unassigned)"
        print(f"  {a['table_name']:<22}{product:<28}{a['platform']:<12}{tb:>10.2f}")


if __name__ == "__main__":
    print_inventories()
