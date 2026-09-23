import frappe

def apply_custom_gst(doc, method):
    """
    Set totals using custom_total_tax_amount calculated from client script.
    Updates:
        - doc.rounded_total
        - doc.grand_total
        - doc.rounding_adjustment
    """

    # If field missing or blank → stop silently
    custom_tax = float(doc.custom_total_tax_amount or 0)

    # Base amount = total without taxes
    net_total = float(doc.total or 0)

    # Compute new grand total with your custom GST
    new_grand_total = net_total + custom_tax

    # Rounding (same logic as ERPNext uses internally)
    rounded_total = round(new_grand_total)

    # Difference = rounding adjustment
    rounding_adjustment = rounded_total - new_grand_total

    # Apply updates to the document
    doc.grand_total = new_grand_total
    doc.rounded_total = rounded_total
    doc.rounding_adjustment = rounding_adjustment

    # Also sync these to DB fields used by ERPNext
    doc.total_taxes_and_charges = custom_tax
    doc.base_total_taxes_and_charges = custom_tax

    # Debug logs for your console
    frappe.logger().info("-------------------------------------")
    frappe.logger().info(f"Custom GST: {custom_tax}")
    frappe.logger().info(f"Net Total: {net_total}")
    frappe.logger().info(f"New Grand Total: {new_grand_total}")
    frappe.logger().info(f"Rounded Total: {rounded_total}")
    frappe.logger().info(f"Adjustment: {rounding_adjustment}")
    frappe.logger().info("-------------------------------------")
