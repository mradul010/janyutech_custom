import frappe


REPORTS = (
	{
		"name": "Purchase Order Payment Tracking Report",
		"ref_doctype": "Purchase Order",
	},
	{
		"name": "Purchase Order Payment Due Date Report",
		"ref_doctype": "Purchase Order",
	},
)
REPORT_ROLES = ("Accounts User", "Accounts Manager", "Purchase User", "Purchase Manager")


def execute():
	for report_config in REPORTS:
		ensure_report(report_config)


def ensure_report(report_config):
	values = {
		"doctype": "Report",
		"report_name": report_config["name"],
		"ref_doctype": report_config["ref_doctype"],
		"report_type": "Script Report",
		"is_standard": "Yes",
		"module": "Janyutech Custom",
		"disabled": 0,
	}

	if frappe.db.exists("Report", report_config["name"]):
		report = frappe.get_doc("Report", report_config["name"])
		report.update(values)
	else:
		report = frappe.get_doc(values)

	existing_roles = {role.role for role in report.get("roles")}
	for role in REPORT_ROLES:
		if role not in existing_roles:
			report.append("roles", {"role": role})

	report.save(ignore_permissions=True)
