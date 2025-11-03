import frappe

def _update_doctype_field_reqd(doctype, fieldname, reqd=False):
    """
    Update DocType field property (for core fields saved in DocType).
    """
    try:
        dt = frappe.get_doc("DocType", doctype)
        changed = False
        for f in dt.fields:
            if f.fieldname == fieldname:
                if bool(f.reqd) != bool(reqd):
                    f.reqd = 1 if reqd else 0
                    changed = True
                # optionally make read_only if reqd==False? (not here)
                break
        if changed:
            dt.save()
            frappe.db.commit()
            frappe.log(f"Updated {doctype}.{fieldname} reqd -> {reqd}")
            return True
    except Exception as e:
        frappe.log(f"Error updating DocType field: {e}")
    return False

def _update_custom_field_reqd(dt, fieldname, reqd=False):
    """
    If item_code is a Custom Field, update that custom field's reqd property.
    """
    cf_name = f"{dt}-{fieldname}"
    if frappe.db.exists("Custom Field", cf_name):
        cf = frappe.get_doc("Custom Field", cf_name)
        cf.reqd = 1 if reqd else 0
        cf.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.log(f"Updated Custom Field {cf_name} reqd -> {reqd}")
        return True
    return False

def execute():
    # 1) Update core DocType field (if item_code defined in DocType)
    core_updated = _update_doctype_field_reqd("Item", "item_code", reqd=False)
    # 2) Update Custom Field (if item_code exists as Custom Field)
    custom_updated = _update_custom_field_reqd("Item", "item_code", reqd=False)

    frappe.clear_cache()
    frappe.msgprint(f"Done. DocType updated: {core_updated}. Custom Field updated: {custom_updated}.")
