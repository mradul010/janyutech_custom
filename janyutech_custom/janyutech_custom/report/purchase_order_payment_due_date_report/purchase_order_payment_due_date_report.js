frappe.query_reports["Purchase Order Payment Due Date Report"] = {
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
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
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
			fieldname: "payment_due_status",
			label: __("Payment Due Status"),
			fieldtype: "Select",
			options: "\nOverdue\nDue Today\nDue Tomorrow\nDue Within 7 Days\nDue Within 15 Days\nDue Within 30 Days\nFuture Payment\nDue Date Not Available\nFully Paid",
		},
		{
			fieldname: "currency",
			label: __("Currency"),
			fieldtype: "Link",
			options: "Currency",
		},
		{
			fieldname: "due_period",
			label: __("Due Period"),
			fieldtype: "Select",
			options: "All Pending Payments\nOverdue Payments\nDue Today\nDue Tomorrow\nNext 7 Days\nNext 15 Days\nNext 30 Days\nCurrent Month\nNext Month",
			default: "All Pending Payments",
		},
		{
			fieldname: "show_only_overdue_payments",
			label: __("Show Only Overdue Payments"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_payments_due_today",
			label: __("Show Payments Due Today"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_fully_paid_payments",
			label: __("Show Fully Paid Payments"),
			fieldtype: "Check",
		},
		{
			fieldname: "group_by_supplier",
			label: __("Group By Supplier"),
			fieldtype: "Check",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "payment_due_status" && data && data.payment_status_color) {
			value = `<span style="color: ${data.payment_status_color}; font-weight: 600;">${value}</span>`;
		}
		return value;
	},
};
