import frappe


REPORTS = (
	"Purchase Order Payment Tracking Report",
	"Purchase Order Payment Due Date Report",
)


def execute():
	if not frappe.db.exists("Workspace", "Buying"):
		return

	workspace = frappe.get_doc("Workspace", "Buying")
	current_links = {
		link.link_to for link in workspace.get("links") if link.link_type == "Report"
	}

	for report_name in REPORTS:
		if report_name in current_links:
			continue
		workspace.append(
			"links",
			{
				"type": "Link",
				"label": report_name,
				"link_to": report_name,
				"link_type": "Report",
				"is_query_report": 1,
				"hidden": 0,
			},
		)

	workspace.save(ignore_permissions=True)
