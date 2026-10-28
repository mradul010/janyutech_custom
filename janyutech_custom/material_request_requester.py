import frappe


def set_requested_by(doc, method=None):
    doc.custom_requested_by = get_requested_by_names(doc)


@frappe.whitelist()
def get_requested_by(doctype, name=None, doc=None):
    if doc:
        doc = frappe.parse_json(doc)
    elif name:
        doc = frappe.get_doc(doctype, name)
    else:
        return ""

    return get_requested_by_names(doc)


def get_requested_by_names(doc):
    material_request_names = _get_material_request_names(doc)
    if not material_request_names:
        return ""

    material_requests = frappe.get_all(
        "Material Request",
        filters={"name": ["in", material_request_names]},
        fields=["name", "owner"],
    )
    owners = {request.owner for request in material_requests if request.owner}
    if not owners:
        return ""

    users = frappe.get_all(
        "User",
        filters={"name": ["in", list(owners)]},
        fields=["name", "full_name"],
    )
    full_names = {user.name: user.full_name or user.name for user in users}

    requested_by = []
    for request in material_requests:
        full_name = full_names.get(request.owner)
        if full_name and full_name not in requested_by:
            requested_by.append(full_name)

    return ", ".join(requested_by)


def _get_material_request_names(doc):
    if doc.get("doctype") == "Purchase Receipt":
        return _get_purchase_receipt_material_requests(doc)

    material_request_names = []
    material_request_items = []
    for row in doc.get("items", []):
        _append_reference(
            material_request_names,
            material_request_items,
            row.get("material_request"),
            row.get("material_request_item"),
        )

    return _resolve_material_request_items(material_request_names, material_request_items)


def _get_purchase_receipt_material_requests(doc):
    material_request_names = []
    material_request_items = []
    purchase_order_item_names = []

    for row in doc.get("items", []):
        if row.get("purchase_order_item"):
            purchase_order_item_names.append(row.get("purchase_order_item"))
        else:
            _append_reference(
                material_request_names,
                material_request_items,
                row.get("material_request"),
                row.get("material_request_item"),
            )

    if purchase_order_item_names:
        purchase_order_items = frappe.get_all(
            "Purchase Order Item",
            filters={"name": ["in", list(set(purchase_order_item_names))]},
            fields=["name", "material_request", "material_request_item"],
        )
        for row in purchase_order_items:
            _append_reference(
                material_request_names,
                material_request_items,
                row.material_request,
                row.material_request_item,
            )

    return _resolve_material_request_items(material_request_names, material_request_items)


def _append_reference(material_request_names, material_request_items, material_request, material_request_item):
    if material_request and material_request not in material_request_names:
        material_request_names.append(material_request)
    elif material_request_item and material_request_item not in material_request_items:
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
