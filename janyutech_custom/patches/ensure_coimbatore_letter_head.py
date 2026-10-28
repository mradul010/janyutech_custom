import frappe


LETTER_HEAD_NAME = "JANYU - Coimbatore"
COMPANY_NAME = "JANYU TECHNOLOGIES PRIVATE LIMITED"
COPY_FIELDS = (
    "source",
    "footer_source",
    "content",
    "footer",
    "image",
    "image_height",
    "image_width",
    "align",
    "footer_image",
    "footer_image_height",
    "footer_image_width",
    "footer_align",
    "header_script",
    "footer_script",
)


def execute():
    if frappe.db.exists("Letter Head", LETTER_HEAD_NAME):
        return

    source_name = frappe.db.get_value("Company", COMPANY_NAME, "default_letter_head")
    source_name = source_name or frappe.db.get_value("Letter Head", {"is_default": 1}, "name")
    if not source_name:
        return

    source = frappe.get_doc("Letter Head", source_name)
    letter_head = frappe.new_doc("Letter Head")
    letter_head.letter_head_name = LETTER_HEAD_NAME
    letter_head.disabled = 0
    letter_head.is_default = 0
    for fieldname in COPY_FIELDS:
        letter_head.set(fieldname, source.get(fieldname))

    letter_head.insert(ignore_permissions=True)
