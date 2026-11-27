from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

from janyutech_custom.janyutech_custom.report.purchase_order_payment_tracking_report.purchase_order_payment_tracking_report import (
	allocate_to_schedule,
	get_invoice_links,
	get_paid_amounts,
	get_payment_schedules,
	get_purchase_orders,
	get_term_paid_amounts,
	schedule_total,
)


STATUS_COLORS = {
	"Overdue": "red",
	"Due Today": "orange",
	"Due Tomorrow": "blue",
	"Due Within 7 Days": "blue",
	"Due Within 15 Days": "blue",
	"Due Within 30 Days": "blue",
	"Future Payment": "gray",
	"Due Date Not Available": "gray",
	"Fully Paid": "green",
	"Overpaid": "blue",
}

STATUS_ORDER = {
	"Overdue": 0,
	"Due Today": 1,
	"Due Tomorrow": 2,
	"Due Within 7 Days": 3,
	"Due Within 15 Days": 4,
	"Due Within 30 Days": 5,
	"Future Payment": 6,
	"Due Date Not Available": 7,
	"Fully Paid": 8,
	"Overpaid": 8,
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.as_on_date = filters.as_on_date or nowdate()

	orders = get_purchase_orders(filters)
	if not orders:
		return get_columns(bool(filters.group_by_supplier)), [], None, None, []

	order_names = [order.name for order in orders]
	schedules = get_payment_schedules(order_names)
	invoice_links = get_invoice_links(order_names)
	paid_amounts = get_paid_amounts(orders, invoice_links, filters.as_on_date)
	term_paid_amounts = get_term_paid_amounts(order_names, filters.as_on_date)

	rows = []
	for order in orders:
		order_schedules = schedules.get(order.name, [])
		paid_amount = paid_amounts.get(order.name, 0)
		payment_rows = allocate_to_schedule(
			order_schedules,
			paid_amount,
			term_paid_amounts.get(order.name, {}).copy(),
			filters.as_on_date,
		)
		if not payment_rows:
			payment_rows = [make_fallback_installment(order, paid_amount)]

		invoice_names = sorted({link.parent for links in invoice_links.values() for link in links if link.purchase_order == order.name})
		for installment in payment_rows:
			row = make_detail_row(order, installment, invoice_names, filters.as_on_date)
			if include_row(row, filters):
				rows.append(row)

	rows.sort(key=sort_key)
	if filters.group_by_supplier:
		rows = group_by_supplier(rows)

	return (
		get_columns(bool(filters.group_by_supplier)),
		rows,
		None,
		None,
		get_report_summary(rows, bool(filters.group_by_supplier)),
	)


def get_columns(group_by_supplier=False):
	if group_by_supplier:
		return [
			link_column("Supplier", "supplier", "Supplier", 140),
			data_column("Supplier Name", "supplier_name", 160),
			link_column("Company", "company", "Company", 140),
			link_column("Currency", "currency", "Currency", 90),
			int_column("Purchase Orders with Pending Payments", "purchase_orders_with_pending_payments"),
			int_column("Pending Installments", "pending_installments"),
			currency_column("Total Outstanding Amount", "total_outstanding_amount"),
			currency_column("Overdue Amount", "overdue_amount"),
			currency_column("Due Today", "due_today_amount"),
			currency_column("Due Within Next 7 Days", "due_7_days_amount"),
			currency_column("Due Within Next 15 Days", "due_15_days_amount"),
			currency_column("Due Within Next 30 Days", "due_30_days_amount"),
			date_column("Earliest Pending Payment Due Date", "earliest_due_date"),
		]

	return [
		link_column("Supplier", "supplier", "Supplier", 140),
		data_column("Supplier Name", "supplier_name", 160),
		link_column("Purchase Order", "purchase_order", "Purchase Order", 150),
		date_column("Purchase Order Date", "purchase_order_date"),
		link_column("Purchase Invoice", "purchase_invoice", "Purchase Invoice", 150),
		link_column("Company", "company", "Company", 140),
		data_column("Payment Term", "payment_term", 140),
		date_column("Payment Due Date", "payment_due_date"),
		currency_column("Total PO Amount", "total_po_amount"),
		currency_column("Scheduled Payment Amount", "scheduled_payment_amount"),
		currency_column("Paid Amount", "paid_amount"),
		currency_column("Pending Payment Amount", "pending_payment_amount"),
		int_column("Days Until Due", "days_until_due"),
		int_column("Overdue Days", "overdue_days"),
		data_column("Payment Status", "payment_due_status", 150),
		link_column("Currency", "currency", "Currency", 90),
	]


def make_detail_row(order, installment, invoice_names, as_on_date):
	status = classify_due_status(installment, as_on_date)
	company_currency = frappe.get_cached_value("Company", order.company, "default_currency")
	return {
		"supplier": order.supplier,
		"supplier_name": order.supplier_name,
		"purchase_order": order.name,
		"purchase_order_date": order.transaction_date,
		"purchase_invoice": invoice_names[0] if len(invoice_names) == 1 else None,
		"company": order.company,
		"payment_term": installment.get("payment_term") or "",
		"payment_due_date": installment.get("due_date"),
		"total_po_amount": schedule_total(order, []),
		"scheduled_payment_amount": installment.get("scheduled_amount", 0),
		"paid_amount": installment.get("paid_amount", 0),
		"pending_payment_amount": max(flt(installment.get("outstanding_amount")), 0),
		"days_until_due": days_until_due(installment.get("due_date"), as_on_date),
		"overdue_days": installment.get("overdue_days", 0),
		"payment_due_status": status,
		"payment_status_color": STATUS_COLORS[status],
		"currency": order.currency,
		"aging_bucket": aging_bucket(installment, as_on_date),
		"_company_currency": company_currency,
		"_base_pending_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0),
		"_base_overdue_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0)
		if status == "Overdue"
		else 0,
		"_base_due_today_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0)
		if status == "Due Today"
		else 0,
		"_base_due_7_days_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0)
		if status in {"Due Today", "Due Tomorrow", "Due Within 7 Days"}
		else 0,
		"_base_due_15_days_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0)
		if status in {"Due Today", "Due Tomorrow", "Due Within 7 Days", "Due Within 15 Days"}
		else 0,
		"_base_due_30_days_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0)
		if status in {
			"Due Today",
			"Due Tomorrow",
			"Due Within 7 Days",
			"Due Within 15 Days",
			"Due Within 30 Days",
		}
		else 0,
		"_base_aging_amount": max(flt(installment.get("outstanding_amount")) * flt(order.conversion_rate), 0),
	}


def make_fallback_installment(order, paid_amount):
	total = flt(order.total)
	remaining = flt(total - paid_amount)
	return frappe._dict(
		{
			"payment_term": None,
			"due_date": None,
			"scheduled_amount": total,
			"paid_amount": paid_amount,
			"outstanding_amount": remaining,
			"status": "Fully Paid" if remaining <= 0 else "Unpaid",
			"overdue_days": 0,
		}
	)


def classify_due_status(installment, as_on_date):
	if installment.get("outstanding_amount", 0) <= 0:
		return "Fully Paid"
	if not installment.get("due_date"):
		return "Due Date Not Available"

	days = (getdate(installment.get("due_date")) - getdate(as_on_date)).days
	if days < 0:
		return "Overdue"
	if days == 0:
		return "Due Today"
	if days == 1:
		return "Due Tomorrow"
	if days <= 7:
		return "Due Within 7 Days"
	if days <= 15:
		return "Due Within 15 Days"
	if days <= 30:
		return "Due Within 30 Days"
	return "Future Payment"


def aging_bucket(installment, as_on_date):
	if installment.get("outstanding_amount", 0) <= 0:
		return "Fully Paid"
	if not installment.get("due_date"):
		return "Due Date Not Available"

	days = (getdate(as_on_date) - getdate(installment.get("due_date"))).days
	if days <= 0:
		return "Due Today" if days == 0 else "Upcoming Payments"
	if days <= 7:
		return "Overdue by 1–7 Days"
	if days <= 15:
		return "Overdue by 8–15 Days"
	if days <= 30:
		return "Overdue by 16–30 Days"
	if days <= 60:
		return "Overdue by 31–60 Days"
	if days <= 90:
		return "Overdue by 61–90 Days"
	return "Overdue by More Than 90 Days"


def include_row(row, filters):
	status = row["payment_due_status"]
	if status == "Fully Paid" and not filters.show_fully_paid_payments:
		return False
	if filters.currency and row["currency"] != filters.currency:
		return False
	if filters.payment_due_status and status != filters.payment_due_status:
		return False
	if filters.show_only_overdue_payments and status != "Overdue":
		return False
	if filters.show_payments_due_today and status != "Due Today":
		return False
	if filters.due_date_from and (
		not row["payment_due_date"] or getdate(row["payment_due_date"]) < getdate(filters.due_date_from)
	):
		return False
	if filters.due_date_to and (
		not row["payment_due_date"] or getdate(row["payment_due_date"]) > getdate(filters.due_date_to)
	):
		return False
	return due_period_matches(row, filters.due_period, filters.as_on_date)


def due_period_matches(row, due_period, as_on_date):
	if not due_period or due_period == "All Pending Payments":
		return True
	status = row["payment_due_status"]
	if due_period == "Overdue Payments":
		return status == "Overdue"
	if due_period == "Due Today":
		return status == "Due Today"
	if due_period == "Due Tomorrow":
		return status == "Due Tomorrow"
	if due_period == "Next 7 Days":
		return status in {"Due Tomorrow", "Due Within 7 Days"}
	if due_period == "Next 15 Days":
		return status in {"Due Tomorrow", "Due Within 7 Days", "Due Within 15 Days"}
	if due_period == "Next 30 Days":
		return status in {
			"Due Tomorrow",
			"Due Within 7 Days",
			"Due Within 15 Days",
			"Due Within 30 Days",
		}
	if not row["payment_due_date"]:
		return False

	due_date = getdate(row["payment_due_date"])
	on_date = getdate(as_on_date)
	if due_period == "Current Month":
		return due_date >= on_date and due_date.month == on_date.month and due_date.year == on_date.year
	if due_period == "Next Month":
		next_month = add_days(on_date.replace(day=28), 4).replace(day=1)
		return due_date.year == next_month.year and due_date.month == next_month.month
	return True


def group_by_supplier(rows):
	groups = {}
	for row in rows:
		key = (row["supplier"], row["company"], row["_company_currency"])
		group = groups.setdefault(
			key,
			{
				"supplier": row["supplier"],
				"supplier_name": row["supplier_name"],
				"company": row["company"],
				"currency": row["_company_currency"],
				"purchase_orders_with_pending_payments": set(),
				"pending_installments": 0,
				"total_outstanding_amount": 0,
				"overdue_amount": 0,
				"due_today_amount": 0,
				"due_7_days_amount": 0,
				"due_15_days_amount": 0,
				"due_30_days_amount": 0,
				"earliest_due_date": None,
				"_aging_amounts": defaultdict(float),
			}
		)
		if row["pending_payment_amount"] > 0:
			group["purchase_orders_with_pending_payments"].add(row["purchase_order"])
			group["pending_installments"] += 1
			group["total_outstanding_amount"] += row["_base_pending_amount"]
			group["overdue_amount"] += row["_base_overdue_amount"]
			group["due_today_amount"] += row["_base_due_today_amount"]
			group["due_7_days_amount"] += row["_base_due_7_days_amount"]
			group["due_15_days_amount"] += row["_base_due_15_days_amount"]
			group["due_30_days_amount"] += row["_base_due_30_days_amount"]
			group["_aging_amounts"][row["aging_bucket"]] += row["_base_aging_amount"]
		if row["pending_payment_amount"] > 0 and row["payment_due_date"]:
			if not group["earliest_due_date"] or row["payment_due_date"] < group["earliest_due_date"]:
				group["earliest_due_date"] = row["payment_due_date"]

	result = []
	for group in groups.values():
		group["purchase_orders_with_pending_payments"] = len(group["purchase_orders_with_pending_payments"])
		result.append(group)
	return sorted(result, key=lambda row: (row["earliest_due_date"] is None, row["earliest_due_date"] or "9999-12-31"))


def get_report_summary(rows, grouped):
	if grouped:
		pending_rows = [row for row in rows if row["pending_installments"]]
		monetary_rows = [
			{
				"_company_currency": row["currency"],
				"_base_pending_amount": row["total_outstanding_amount"],
				"_base_overdue_amount": row["overdue_amount"],
				"_base_due_today_amount": row["due_today_amount"],
				"_base_due_7_days_amount": row["due_7_days_amount"],
				"_base_due_30_days_amount": row["due_30_days_amount"],
			}
			for row in rows
		]
	else:
		pending_rows = [row for row in rows if row["pending_payment_amount"] > 0]
		monetary_rows = rows

	return [
		{"label": _("Suppliers with Pending Payments"), "value": len({row["supplier"] for row in pending_rows}), "datatype": "Int"},
		{"label": _("Purchase Orders with Pending Payments"), "value": len({row["purchase_order"] for row in pending_rows}), "datatype": "Int"},
		currency_summary("Total Pending Payment Amount", monetary_rows, "_base_pending_amount"),
		currency_summary("Total Overdue Amount", monetary_rows, "_base_overdue_amount"),
		currency_summary("Amount Due Today", monetary_rows, "_base_due_today_amount"),
		currency_summary("Amount Due in Next 7 Days", monetary_rows, "_base_due_7_days_amount"),
		currency_summary("Amount Due in Next 30 Days", monetary_rows, "_base_due_30_days_amount"),
		{
			"label": _("Total Pending Installments"),
			"value": sum(row["pending_installments"] if grouped else int(row["pending_payment_amount"] > 0) for row in rows),
			"datatype": "Int",
		},
	] + get_aging_summary(rows, grouped)


def get_aging_summary(rows, grouped):
	buckets = (
		"Due Today",
		"Overdue by 1–7 Days",
		"Overdue by 8–15 Days",
		"Overdue by 16–30 Days",
		"Overdue by 31–60 Days",
		"Overdue by 61–90 Days",
		"Overdue by More Than 90 Days",
		"Upcoming Payments",
		"Due Date Not Available",
	)
	result = []
	for bucket in buckets:
		if grouped:
			bucket_rows = [
				{"_company_currency": row["currency"], "_base_aging_amount": row["_aging_amounts"].get(bucket, 0)}
				for row in rows
			]
		else:
			bucket_rows = [
				{
					"_company_currency": row["_company_currency"],
					"_base_aging_amount": row["_base_aging_amount"],
				}
				for row in rows
				if row["aging_bucket"] == bucket
			]
		result.append(currency_summary(f"Aging: {bucket}", bucket_rows, "_base_aging_amount"))
	return result


def currency_summary(label, rows, fieldname):
	totals = defaultdict(float)
	for row in rows:
		totals[row["_company_currency"]] += flt(row.get(fieldname))
	if len(totals) == 1:
		currency, value = next(iter(totals.items()))
		return {"label": _(label), "value": value, "datatype": "Currency", "currency": currency}
	return {
		"label": _(label),
		"value": ", ".join(f"{currency} {value:,.2f}" for currency, value in sorted(totals.items())),
		"datatype": "Data",
	}


def sort_key(row):
	return (
		STATUS_ORDER.get(row.get("payment_due_status"), 99),
		row.get("payment_due_date") is None,
		row.get("payment_due_date") or "9999-12-31",
		row.get("supplier_name") or "",
		row.get("purchase_order") or "",
	)


def days_until_due(due_date, as_on_date):
	return (getdate(due_date) - getdate(as_on_date)).days if due_date else 0


def link_column(label, fieldname, options, width):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Link", "options": options, "width": width}


def data_column(label, fieldname, width):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Data", "width": width}


def currency_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Currency", "width": 130}


def date_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Date", "width": 110}


def int_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Int", "width": 120}
