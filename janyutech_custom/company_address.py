import re

import frappe
from frappe.contacts.doctype.address.address import get_address_display


SERIES_LOCATION_MAP = {
    "Purchase Order": {
        "PUR-ORD-.YYYY.-": "Vasai East",
        "PUR-ORD-CM-.YYYY.-": "COIMBATORE",
    },
    "Purchase Receipt": {
        "PR-.YYYY.-": "Vasai East",
        "PR-CM-.YYYY.-": "COIMBATORE",
    },
}


def normalize_location(value):
    return re.sub(r"\s+", " ", frappe.as_unicode(value or "").strip()).casefold()


def get_location_from_series(doctype, naming_series):
    return SERIES_LOCATION_MAP.get(doctype, {}).get(naming_series)


@frappe.whitelist()
def get_company_addresses_for_series(doctype, company, naming_series):
    location = get_location_from_series(doctype, naming_series)
    if not location or not company:
        return {}

    result = {
        "location": location,
        "billing_address": None,
        "billing_address_display": "",
        "shipping_address": None,
        "shipping_address_display": "",
    }

    billing_address = get_company_address(company, location, "Billing")
    shipping_address = get_company_address(company, location, "Shipping")

    if billing_address:
        result["billing_address"] = billing_address
        result["billing_address_display"] = get_address_display(billing_address) or ""

    if shipping_address:
        result["shipping_address"] = shipping_address
        result["shipping_address_display"] = get_address_display(shipping_address) or ""

    return result


def get_company_address(company, location, address_type):
    target_location = normalize_location(location)
    addresses = frappe.db.sql(
        """
        SELECT addr.name, addr.city
        FROM `tabAddress` addr
        INNER JOIN `tabDynamic Link` link
            ON link.parent = addr.name
            AND link.parenttype = 'Address'
            AND link.link_doctype = 'Company'
            AND link.link_name = %(company)s
        WHERE IFNULL(addr.disabled, 0) = 0
            AND IFNULL(addr.is_your_company_address, 0) = 1
            AND addr.address_type = %(address_type)s
        ORDER BY addr.is_primary_address DESC,
            addr.is_shipping_address DESC,
            addr.creation ASC
        """,
        {"company": company, "address_type": address_type},
        as_dict=True,
    )

    for address in addresses:
        if normalize_location(address.city) == target_location:
            return address.name

    return None


def set_company_addresses_from_series(doc, method=None):
    addresses = get_company_addresses_for_series(
        doc.doctype,
        doc.get("company"),
        doc.get("naming_series"),
    )
    if not addresses:
        return

    if addresses.get("billing_address"):
        doc.billing_address = addresses.get("billing_address")
        doc.billing_address_display = addresses.get("billing_address_display") or ""

    if addresses.get("shipping_address"):
        doc.shipping_address = addresses.get("shipping_address")
        doc.shipping_address_display = addresses.get("shipping_address_display") or ""
