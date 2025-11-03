import frappe

def create_custom_field_if_missing(field_dict):
    """Create a Custom Field if it doesn't already exist."""
    doctype = field_dict.get("dt")
    fieldname = field_dict.get("fieldname")
    cf_name = f"{doctype}-{fieldname}"
    if frappe.db.exists("Custom Field", cf_name):
        frappe.log("Custom Field exists: " + cf_name)
        return False

    cf = frappe.get_doc({
        "doctype": "Custom Field",
        **field_dict
    })
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.log("Created Custom Field: " + cf_name)
    return True

def add_item_fields():
    # Define the fields to create
    fields = [
        {
            "dt": "Item",
            "label": "Main Category",
            "fieldname": "main_category",
            "fieldtype": "Link",
            "options": "Item Main Category",
            "insert_after": "item_group",
            "in_list_view": 1,
            "print_hide": 0
        },
        {
            "dt": "Item",
            "label": "Sub Category",
            "fieldname": "sub_category",
            "fieldtype": "Link",
            "options": "Item Sub Category",
            "insert_after": "main_category",
            "in_list_view": 1,
            "print_hide": 0
        },
        # abbreviation fields that auto-fetch from linked doctypes
        {
            "dt": "Item",
            "label": "Main Category Abbr",
            "fieldname": "main_category_abbr",
            "fieldtype": "Data",
            "read_only": 1,
            "insert_after": "sub_category",
            "fetch_from": "main_category.abbreviation",
            "hidden": 0
        },
        {
            "dt": "Item",
            "label": "Sub Category Abbr",
            "fieldname": "sub_category_abbr",
            "fieldtype": "Data",
            "read_only": 1,
            "insert_after": "main_category_abbr",
            "fetch_from": "sub_category.abbreviation",
            "hidden": 0
        }
    ]

    created = []
    for f in fields:
        try:
            ok = create_custom_field_if_missing(f)
            if ok:
                created.append(f["fieldname"])
        except Exception as e:
            frappe.log(f"Failed to create custom field {f.get('fieldname')}: {e}")

    return created

def populate_abbr_for_existing_items():
    """
    For any existing Item records that already have main_category/sub_category links,
    set the *_abbr fields so the values are visible immediately (optional but helpful).
    """
    try:
        items = frappe.get_all("Item",
            filters=[["main_category","is","set"] , ["or", ["sub_category","is","set"]]],
            fields=["name","main_category","sub_category","main_category_abbr","sub_category_abbr"],
            limit_page_length=1000
        )
    except Exception:
        return 0

    updated_count = 0
    for itm in items:
        to_save = False
        doc = frappe.get_doc("Item", itm.name)
        if doc.get("main_category") and not doc.get("main_category_abbr"):
            ab = frappe.db.get_value("Item Main Category", doc.main_category, "abbreviation")
            if ab:
                doc.main_category_abbr = ab
                to_save = True
        if doc.get("sub_category") and not doc.get("sub_category_abbr"):
            ab2 = frappe.db.get_value("Item Sub Category", doc.sub_category, "abbreviation")
            if ab2:
                doc.sub_category_abbr = ab2
                to_save = True

        if to_save:
            try:
                doc.save(ignore_permissions=True)
                updated_count += 1
            except Exception:
                frappe.log(f"Could not update Item {doc.name} with category abbrs.")
                continue

    if updated_count:
        frappe.db.commit()
    return updated_count

def execute():
    frappe.reload_doc("core", "doctype", "custom_field")  # ensure meta loaded
    created = add_item_fields()
    updated = populate_abbr_for_existing_items()

    frappe.clear_cache()
    frappe.msgprint(f"Patch complete. Created fields: {', '.join(created) if created else 'none'}. "
                    f"Populated abbr on {updated} existing Item(s).")
