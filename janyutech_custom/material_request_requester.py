import frappe


def set_requested_by(doc, method=None):
    values = get_purchase_request_values_for_doc(doc)
    previous_doc = doc.get_doc_before_save()
    previous_values = get_purchase_request_values_for_doc(previous_doc) if previous_doc else {}

    _set_automatic_value(doc, "custom_requested_by", values["requested_by"], previous_values.get("requested_by"))
    _set_automatic_value(
        doc, "custom_purchase_req_no", values["purchase_req_no"], previous_values.get("purchase_req_no")
    )


@frappe.whitelist()
def get_requested_by(doctype, name=None, doc=None):
    return _get_doc_values(doctype, name, doc)["requested_by"]


@frappe.whitelist()
def get_purchase_request_values(doctype, name=None, doc=None):
    return _get_doc_values(doctype, name, doc)


def _get_doc_values(doctype, name, doc):
    if doc:
        doc = frappe.parse_json(doc)
    elif name:
        doc = frappe.get_doc(doctype, name)
    else:
        return {"requested_by": "", "purchase_req_no": ""}

    return get_purchase_request_values_for_doc(doc)


def get_requested_by_names(doc):
    return get_purchase_request_values_for_doc(doc)["requested_by"]


def get_purchase_request_values_for_doc(doc):
    material_request_names, purchase_order_values = _get_references(doc)
    material_request_values = _get_material_request_values(material_request_names)

    requested_by = []
    purchase_req_no = []
    for purchase_order in purchase_order_values:
        _append_csv_values(requested_by, purchase_order.get("requested_by"))
        _append_csv_values(purchase_req_no, purchase_order.get("purchase_req_no"))

        if not purchase_order.get("requested_by"):
            for material_request in purchase_order.get("material_requests", []):
                _append_csv_values(
                    requested_by,
                    material_request_values["requested_by_by_name"].get(material_request),
                )
        if not purchase_order.get("purchase_req_no"):
            _append_csv_values(purchase_req_no, purchase_order.get("material_requests"))

    if not purchase_order_values:
        _append_csv_values(requested_by, material_request_values["requested_by"])
        _append_csv_values(purchase_req_no, material_request_names)

    return {"requested_by": ", ".join(requested_by), "purchase_req_no": ", ".join(purchase_req_no)}


def _set_automatic_value(doc, fieldname, new_value, previous_automatic_value):
    current_value = doc.get(fieldname) or ""
    if not current_value or current_value == (previous_automatic_value or ""):
        doc.set(fieldname, new_value or "")


def _get_references(doc):
    material_request_names = []
    material_request_items = []
    purchase_order_item_names = []
    purchase_order_names = []

    for row in doc.get("items", []):
        if doc.get("doctype") == "Purchase Receipt" and row.get("purchase_order_item"):
            purchase_order_item_names.append(row.get("purchase_order_item"))
        elif doc.get("doctype") == "Purchase Receipt" and row.get("purchase_order"):
            purchase_order_names.append(row.get("purchase_order"))
        else:
            _append_reference(material_request_names, material_request_items, row)

    purchase_order_values = _get_purchase_order_values(purchase_order_item_names, purchase_order_names)
    for purchase_order in purchase_order_values:
        for material_request in purchase_order.get("material_requests", []):
            if material_request not in material_request_names:
                material_request_names.append(material_request)
        for material_request_item in purchase_order.get("material_request_items", []):
            if material_request_item not in material_request_items:
                material_request_items.append(material_request_item)

    for row in doc.get("items", []):
        if not row.get("purchase_order_item"):
            _append_reference(material_request_names, material_request_items, row)

    return _resolve_material_request_items(material_request_names, material_request_items), purchase_order_values


def _get_purchase_order_values(purchase_order_item_names, purchase_order_names):
    if not purchase_order_item_names and not purchase_order_names:
        return []

    item_rows = []
    if purchase_order_item_names:
        item_rows = frappe.get_all(
            "Purchase Order Item",
            filters={"name": ["in", list(set(purchase_order_item_names))]},
            fields=["name", "parent", "material_request", "material_request_item"],
        )
    parent_names = list(dict.fromkeys(purchase_order_names))
    parent_names.extend(row.parent for row in item_rows if row.parent and row.parent not in parent_names)
    parent_values = {}
    if parent_names:
        parent_values = {
            row.name: row
            for row in frappe.get_all(
                "Purchase Order",
                filters={"name": ["in", parent_names]},
                fields=["name", "custom_requested_by", "custom_purchase_req_no"],
            )
        }

    values_by_parent = {
        parent_name: {
            "name": parent_name,
            "requested_by": parent_values[parent_name].custom_requested_by or "",
            "purchase_req_no": parent_values[parent_name].custom_purchase_req_no or "",
            "material_requests": [],
        }
        for parent_name in purchase_order_names
        if parent_name in parent_values
    }
    for row in item_rows:
        value = values_by_parent.setdefault(
            row.parent,
            {
                "name": row.parent,
                "requested_by": "",
                "purchase_req_no": "",
                "material_requests": [],
                "material_request_items": [],
            },
        )
        parent = parent_values.get(row.parent)
        if parent:
            value["requested_by"] = parent.custom_requested_by or ""
            value["purchase_req_no"] = parent.custom_purchase_req_no or ""
        if row.material_request and row.material_request not in value["material_requests"]:
            value["material_requests"].append(row.material_request)
        if row.material_request_item and row.material_request_item not in value["material_request_items"]:
            value["material_request_items"].append(row.material_request_item)

    return list(values_by_parent.values())


def _append_reference(material_request_names, material_request_items, row):
    material_request = row.get("material_request")
    material_request_item = row.get("material_request_item")
    if material_request and material_request not in material_request_names:
        material_request_names.append(material_request)
    if material_request_item and material_request_item not in material_request_items:
        material_request_items.append(material_request_item)


def _resolve_material_request_items(material_request_names, material_request_items):
    if not material_request_items:
        return material_request_names

    request_items = frappe.get_all(
        "Material Request Item",
        filters={"name": ["in", list(set(material_request_items))]},
        fields=["name", "parent"],
    )
    for row in request_items:
        if row.parent not in material_request_names:
            material_request_names.append(row.parent)

    return material_request_names


def _get_material_request_values(material_request_names):
    if not material_request_names:
        return {"requested_by": [], "requested_by_by_name": {}}

    material_requests = frappe.get_all(
        "Material Request",
        filters={"name": ["in", material_request_names]},
        fields=["name", "owner"],
    )
    owners = {request.owner for request in material_requests if request.owner}
    users = (
        frappe.get_all(
            "User",
            filters={"name": ["in", list(owners)]},
            fields=["name", "full_name"],
        )
        if owners
        else []
    )
    full_names = {user.name: user.full_name or user.name for user in users}

    requested_by = []
    requested_by_by_name = {}
    for request in material_requests:
        full_name = full_names.get(request.owner)
        if full_name:
            requested_by_by_name[request.name] = [full_name]
            _append_csv_values(requested_by, full_name)

    return {"requested_by": requested_by, "requested_by_by_name": requested_by_by_name}


def _append_csv_values(values, raw_value):
    raw_values = raw_value if isinstance(raw_value, (list, tuple, set)) else (raw_value or "").split(",")
    for value in raw_values:
        value = str(value or "").strip()
        if value and value not in values:
            values.append(value)
