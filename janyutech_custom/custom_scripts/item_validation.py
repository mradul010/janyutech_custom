import frappe
from frappe.utils import escape_html


def validate_unique_item_name(doc, method=None):
    item_name = (doc.get("item_name") or "").strip()
    if not item_name:
        return

    duplicate = frappe.db.sql(
        """
        SELECT name
        FROM `tabItem`
        WHERE LOWER(TRIM(item_name)) = LOWER(TRIM(%(item_name)s))
            AND name != %(name)s
        ORDER BY creation ASC
        LIMIT 1
        """,
        {
            "item_name": item_name,
            "name": doc.name or "",
        },
        as_dict=True,
    )

    if duplicate:
        frappe.throw(
            f'Item Name "{escape_html(item_name)}" already exists in Item {escape_html(duplicate[0].name)}.',
            title="Duplicate Item Name",
        )
