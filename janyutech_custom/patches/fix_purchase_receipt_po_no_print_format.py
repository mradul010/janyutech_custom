import json

import frappe


PRINT_FORMATS = (
    "Purchase Receipt Custom",
    "Purchase Order GST Breakdown Purchase receipt",
)

OLD_PO_NO = '<td class="po-info-label">PO No:</td>\r\n      <td class="po-info-value">{{ doc.name or "-" }}</td>'
NEW_PO_NO = (
    '<td class="po-info-label">PR No:</td>\r\n'
    '      <td class="po-info-value">{{ doc.name or "-" }}</td>\r\n\r\n'
    '      <td class="po-info-label">PO No:</td>\r\n'
    '      <td class="po-info-value">{{ get_purchase_order_numbers(doc) }}</td>'
)


def execute():
    for print_format in PRINT_FORMATS:
        format_data = frappe.db.get_value("Print Format", print_format, "format_data")
        if not format_data:
            continue

        data = json.loads(format_data)
        changed = False

        for field in data:
            options = field.get("options")
            if not isinstance(options, str) or OLD_PO_NO not in options:
                continue

            field["options"] = options.replace(OLD_PO_NO, NEW_PO_NO)
            changed = True

        if changed:
            frappe.db.set_value(
                "Print Format",
                print_format,
                "format_data",
                json.dumps(data, separators=(",", ":")),
                update_modified=False,
            )

