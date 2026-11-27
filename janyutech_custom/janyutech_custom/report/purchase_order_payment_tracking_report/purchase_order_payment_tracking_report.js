frappe.query_reports["Purchase Order Payment Tracking Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "purchase_order",
			label: __("Purchase Order"),
			fieldtype: "Link",
			options: "Purchase Order",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nUnpaid\nPartially Paid\nFully Paid\nOverdue\nOverpaid",
		},
		{
			fieldname: "payment_terms_template",
			label: __("Payment Terms Template"),
			fieldtype: "Link",
			options: "Payment Terms Template",
		},
		{
			fieldname: "currency",
			label: __("Currency"),
			fieldtype: "Link",
			options: "Currency",
		},
		{
			fieldname: "due_date_from",
			label: __("Due Date From"),
			fieldtype: "Date",
		},
		{
			fieldname: "due_date_to",
			label: __("Due Date To"),
			fieldtype: "Date",
		},
		{
			fieldname: "show_only_pending_payments",
			label: __("Show Only Pending Payments"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_only_overdue_payments",
			label: __("Show Only Overdue Payments"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_payment_schedule_details",
			label: __("Show Payment Schedule Details"),
			fieldtype: "Check",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "payment_status" && data && data.payment_status_color) {
			value = `<span style="color: ${data.payment_status_color}; font-weight: 600;">${value}</span>`;
		}
		return value;
	},
};
