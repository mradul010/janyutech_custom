import frappe


def generate_item_code(doc):
    """
    Generate Item Code as: <MAIN_ABBR>-<SUB_ABBR>-<seq>
    Example: MM-HM-001

    This implementation ensures the sequence is maintained per (main_abbr, sub_abbr) prefix.
    """
    if doc.get("item_code"):
        return doc.item_code

    # Ensure categories present
    main = doc.get("main_category")
    sub = doc.get("sub_category")

    if not main:
        frappe.throw("Main Category is required to generate Item Code.")

    if not sub:
        frappe.throw("Sub Category is required to generate Item Code.")

    # Fetch abbreviations from linked doctypes
    main_abbr = frappe.db.get_value("Item Main Category", main, "abbreviation") or ""
    sub_abbr = frappe.db.get_value("Item Sub Category", sub, "abbreviation") or ""

    if not main_abbr:
        frappe.throw("Main Category Abbreviation is missing.")

    if not sub_abbr:
        frappe.throw("Sub Category Abbreviation is missing.")

    # Build prefix like "MM-HM"
    prefix = f"{main_abbr}-{sub_abbr}"

    # Find the max numeric suffix for this prefix (search both name and item_code)
    # Uses SQL to extract the numeric part after the last hyphen and take MAX
    res = frappe.db.sql("""
        SELECT GREATEST(
            COALESCE(MAX(CAST(SUBSTRING_INDEX(item_code, '-', -1) AS UNSIGNED)), 0),
            COALESCE(MAX(CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED)), 0)
        ) as max_seq
        FROM `tabItem`
        WHERE (item_code LIKE %(p)s OR name LIKE %(p)s)
    """, {"p": prefix + "-%"}, as_dict=True)

    next_seq = 1
    if res and res[0].get("max_seq"):
        try:
            next_seq = int(res[0]["max_seq"]) + 1
        except Exception:
            next_seq = 1

    # build candidate name
    candidate = f"{prefix}-{next_seq:03d}"

    # collision check (very rare) — bump until unique (small loop)
    attempts = 0
    while frappe.db.exists("Item", candidate) and attempts < 100:
        attempts += 1
        next_seq += 1
        candidate = f"{prefix}-{next_seq:03d}"

    if frappe.db.exists("Item", candidate):
        # fallback: use make_autoname as a last resort (avoid throwing)
        from frappe.model.naming import make_autoname
        candidate = make_autoname(f"{prefix}-.###")

    return candidate


def before_naming(doc, method=None):
    doc.item_code = generate_item_code(doc)


def autoname(doc, method=None):
    item_code = generate_item_code(doc)
    doc.name = item_code
    doc.item_code = item_code
