from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


PAYMENT_ENTRY_TYPES = ("Payment Entry", "Journal Entry")
STATUS_COLORS = {
	"Fully Paid": "green",
	"Partially Paid": "orange",
	"Unpaid": "gray",
	"Overdue": "red",
	"Overpaid": "blue",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.as_on_date = filters.as_on_date or nowdate()

	columns = get_columns(filters)
	orders = get_purchase_orders(filters)
	if not orders:
		return columns, []

	order_names = [order.name for order in orders]
	schedules = get_payment_schedules(order_names)
	invoice_links = get_invoice_links(order_names)
	paid_amounts = get_paid_amounts(orders, invoice_links, filters.as_on_date)
	term_paid_amounts = get_term_paid_amounts(order_names, filters.as_on_date)

	rows = []
	for order in orders:
		order_schedules = schedules.get(order.name, [])
		payment = build_payment_summary(
			order,
			order_schedules,
			paid_amounts.get(order.name, 0),
			term_paid_amounts.get(order.name, {}),
			filters,
		)
		if filters.show_payment_schedule_details:
			rows.extend(
				row
				for row, installment in zip(payment["detail_rows"], payment["installments"])
				if include_installment_row(installment, filters)
			)
		elif include_summary_row(payment, filters):
			rows.append(payment["summary_row"])

	return columns, rows


def get_columns(filters):
	if filters.show_payment_schedule_details:
		return [
			link_column("Purchase Order", "purchase_order", "Purchase Order", 150),
			link_column("Supplier", "supplier", "Supplier", 140),
			data_column("Supplier Name", "supplier_name", 160),
			link_column("Payment Term", "payment_term", "Payment Term", 140),
			percent_column("Invoice Portion", "invoice_portion"),
			date_column("Payment Due Date", "due_date"),
			currency_column("Scheduled Payment Amount", "scheduled_payment_amount"),
			currency_column("Paid Amount", "paid_amount"),
			currency_column("Outstanding Amount", "outstanding_amount"),
			data_column("Payment Status", "payment_status", 120),
			int_column("Overdue Days", "overdue_days"),
		]

	return [
		link_column("Purchase Order", "purchase_order", "Purchase Order", 150),
		date_column("PO Date", "po_date"),
		link_column("Supplier", "supplier", "Supplier", 140),
		data_column("Supplier Name", "supplier_name", 160),
		link_column("Company", "company", "Company", 140),
		link_column("Currency", "currency", "Currency", 90),
		link_column("Payment Terms Template", "payment_terms_template", "Payment Terms Template", 150),
		currency_column("Total Payment Amount", "total_payment_amount"),
		currency_column("Paid Amount", "paid_amount"),
		currency_column("Outstanding Amount", "outstanding_amount"),
		int_column("Total Scheduled Payments", "total_scheduled_payments"),
		int_column("Completed Payments", "completed_payments"),
		int_column("Pending Payments", "pending_payments"),
		int_column("Overdue Payments", "overdue_payments"),
		date_column("Next Payment Due Date", "next_payment_due_date"),
		currency_column("Next Payment Amount", "next_payment_amount"),
		currency_column("Overdue Amount", "overdue_amount"),
		data_column("Payment Status", "payment_status", 120),
		data_column("Purchase Order Status", "purchase_order_status", 130),
	]


def get_purchase_orders(filters):
	conditions = {"docstatus": ["!=", 2]}
	for fieldname in ("company", "supplier", "name", "payment_terms_template", "currency"):
		value = filters.get("purchase_order") if fieldname == "name" else filters.get(fieldname)
		if value:
			conditions[fieldname] = value

	if filters.from_date and filters.to_date:
		conditions["transaction_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.from_date:
		conditions["transaction_date"] = [">=", filters.from_date]
	elif filters.to_date:
		conditions["transaction_date"] = ["<=", filters.to_date]

	return frappe.get_list(
		"Purchase Order",
		filters=conditions,
		fields=[
			"name",
			"transaction_date",
			"supplier",
			"supplier_name",
			"company",
			"currency",
			"conversion_rate",
			"total",
			"payment_terms_template",
			"status",
		],
		order_by="transaction_date, name",
	)


def get_payment_schedules(order_names):
	rows = frappe.get_all(
		"Payment Schedule",
		filters={"parenttype": "Purchase Order", "parent": ["in", order_names]},
		fields=[
			"parent",
			"name",
			"idx",
			"payment_term",
			"due_date",
			"invoice_portion",
			"payment_amount",
		],
		order_by="parent, due_date, idx",
	)
	result = defaultdict(list)
	for row in rows:
		result[row.parent].append(row)
	return result


def get_invoice_links(order_names):
	rows = frappe.get_all(
		"Purchase Invoice Item",
		filters={"purchase_order": ["in", order_names], "docstatus": 1},
		fields=["parent", "purchase_order", "base_amount", "amount"],
	)
	result = defaultdict(list)
	for row in rows:
		result[row.parent].append(row)
	return result


def get_paid_amounts(orders, invoice_links, as_on_date):
	order_names = [order.name for order in orders]
	po_paid_base = get_ledger_totals("Purchase Order", order_names, as_on_date)

	invoice_names = list(invoice_links)
	invoice_paid_base = get_ledger_totals("Purchase Invoice", invoice_names, as_on_date)
	invoice_allocated_base = get_invoice_allocations(invoice_names, as_on_date)

	result = defaultdict(float)
	for order in orders:
		base_paid = po_paid_base.get(order.name, 0)
		for invoice_name, links in invoice_links.items():
			order_links = [link for link in links if link.purchase_order == order.name]
			if not order_links:
				continue
			denominator = sum(invoice_item_base_amount(link) for link in links)
			share = (
				sum(invoice_item_base_amount(link) for link in order_links) / denominator
				if denominator
				else 0
			)
			base_paid += invoice_paid_base.get(invoice_name, 0) * share

		# Allocations made from an existing PO advance are already represented by
		# the PO ledger total; exclude them from invoice cash totals above.
		for invoice_name, allocated_base in invoice_allocated_base.items():
			links = invoice_links.get(invoice_name, [])
			order_links = [link for link in links if link.purchase_order == order.name]
			if not order_links:
				continue
			denominator = sum(invoice_item_base_amount(link) for link in links)
			share = (
				sum(invoice_item_base_amount(link) for link in order_links) / denominator
				if denominator
				else 0
			)
			base_paid -= allocated_base * share

		result[order.name] = flt(base_paid / flt(order.conversion_rate)) if order.conversion_rate else 0
	return result


def invoice_item_base_amount(row):
	return flt(row.base_amount) or flt(row.amount)


def get_ledger_totals(against_doctype, names, as_on_date):
	if not names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT against_voucher_no AS voucher_no, SUM(-amount) AS paid_amount
		FROM `tabPayment Ledger Entry`
		WHERE against_voucher_type = %(doctype)s
		  AND against_voucher_no IN %(names)s
		  AND voucher_type IN %(voucher_types)s
		  AND posting_date <= %(as_on_date)s
		  AND delinked = 0
		GROUP BY against_voucher_no
		""",
		{
			"doctype": against_doctype,
			"names": tuple(names),
			"voucher_types": PAYMENT_ENTRY_TYPES,
			"as_on_date": as_on_date,
		},
		as_dict=True,
	)
	return {row.voucher_no: flt(row.paid_amount) for row in rows}


def get_invoice_allocations(invoice_names, as_on_date):
	if not invoice_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT per.reference_name AS invoice_name,
		       SUM(per.allocated_amount * COALESCE(pe.target_exchange_rate, 1)) AS amount
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE per.reference_doctype = 'Purchase Invoice'
		  AND per.reference_name IN %(invoice_names)s
		  AND per.parenttype = 'Payment Entry'
		  AND pe.docstatus = 1
		  AND pe.posting_date <= %(as_on_date)s
		  AND per.advance_voucher_type IN ('Payment Entry', 'Purchase Order')
		GROUP BY per.reference_name
		""",
		{"invoice_names": tuple(invoice_names), "as_on_date": as_on_date},
		as_dict=True,
	)
	return {row.invoice_name: flt(row.amount) for row in rows}


def get_term_paid_amounts(order_names, as_on_date):
	rows = frappe.db.sql(
		"""
		SELECT per.reference_name AS purchase_order, per.payment_term,
		       SUM(per.allocated_amount) AS allocated_amount
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE per.reference_doctype = 'Purchase Order'
		  AND per.reference_name IN %(order_names)s
		  AND per.parenttype = 'Payment Entry'
		  AND pe.docstatus = 1
		  AND pe.posting_date <= %(as_on_date)s
		GROUP BY per.reference_name, per.payment_term
		""",
		{"order_names": tuple(order_names), "as_on_date": as_on_date},
		as_dict=True,
	)
	result = defaultdict(dict)
	for row in rows:
		if row.payment_term:
			result[row.purchase_order][row.payment_term] = flt(row.allocated_amount)
	return result


def build_payment_summary(order, schedules, paid_amount, term_paid_amounts, filters):
	total = schedule_total(order, schedules)
	installments = allocate_to_schedule(schedules, paid_amount, term_paid_amounts, filters.as_on_date)
	precision = frappe.get_precision("Purchase Order", "total") or 2
	outstanding = flt(total - paid_amount, precision)
	status = get_status(total, paid_amount, installments, filters.as_on_date, precision)
	pending = [item for item in installments if item["outstanding_amount"] > 0]
	overdue = [item for item in pending if item["due_date"] and getdate(item["due_date"]) < getdate(filters.as_on_date)]

	summary = {
		"purchase_order": order.name,
		"po_date": order.transaction_date,
		"supplier": order.supplier,
		"supplier_name": order.supplier_name,
		"company": order.company,
		"currency": order.currency,
		"payment_terms_template": order.payment_terms_template,
		"total_payment_amount": total,
		"paid_amount": paid_amount,
		"outstanding_amount": outstanding,
		"total_scheduled_payments": len(installments),
		"completed_payments": sum(1 for item in installments if item["outstanding_amount"] <= 0),
		"pending_payments": len(pending),
		"overdue_payments": len(overdue),
		"next_payment_due_date": pending[0]["due_date"] if pending else None,
		"next_payment_amount": pending[0]["outstanding_amount"] if pending else 0,
		"overdue_amount": sum(item["outstanding_amount"] for item in overdue),
		"payment_status": status,
		"payment_status_color": STATUS_COLORS[status],
		"purchase_order_status": order.status,
	}

	detail_rows = []
	for item in installments:
		detail_rows.append(
			{
				"purchase_order": order.name,
				"supplier": order.supplier,
				"supplier_name": order.supplier_name,
				"payment_term": item["payment_term"],
				"invoice_portion": item["invoice_portion"],
				"due_date": item["due_date"],
				"scheduled_payment_amount": item["scheduled_amount"],
				"paid_amount": item["paid_amount"],
				"outstanding_amount": item["outstanding_amount"],
				"payment_status": item["status"],
				"payment_status_color": STATUS_COLORS[item["status"]],
				"overdue_days": item["overdue_days"],
			}
		)

	return {"summary_row": summary, "detail_rows": detail_rows, "status": status, "installments": installments}


def schedule_total(order, schedules):
	if schedules:
		return flt(sum(flt(row.payment_amount) for row in schedules))
	return flt(order.total)


def allocate_to_schedule(schedules, paid_amount, term_paid_amounts, as_on_date):
	if not schedules:
		return []

	remaining = max(flt(paid_amount), 0)
	result = []
	for row in sorted(schedules, key=lambda item: (item.due_date or "9999-12-31", item.idx)):
		term_paid = term_paid_amounts.get(row.payment_term)
		if term_paid is not None:
			allocated = min(flt(row.payment_amount), max(term_paid, 0))
			term_paid_amounts[row.payment_term] = max(term_paid - allocated, 0)
			remaining = max(remaining - allocated, 0)
		else:
			allocated = min(flt(row.payment_amount), remaining)
			remaining -= allocated
		result.append(schedule_row(row, allocated, as_on_date))

	# A payment not matched to an installment is an overpayment; do not hide it.
	if remaining and result:
		result[-1]["paid_amount"] += remaining
		result[-1]["outstanding_amount"] = flt(result[-1]["scheduled_amount"] - result[-1]["paid_amount"])
		result[-1]["status"] = "Overpaid"
	return result


def schedule_row(row, paid_amount, as_on_date):
	outstanding = flt(row.payment_amount) - flt(paid_amount)
	is_overdue = outstanding > 0 and row.due_date and getdate(row.due_date) < getdate(as_on_date)
	status = "Fully Paid" if outstanding <= 0 else "Overdue" if is_overdue else "Partially Paid" if paid_amount else "Unpaid"
	return {
		"payment_term": row.payment_term,
		"invoice_portion": row.invoice_portion,
		"due_date": row.due_date,
		"scheduled_amount": flt(row.payment_amount),
		"paid_amount": flt(paid_amount),
		"outstanding_amount": flt(outstanding),
		"status": status,
		"overdue_days": max((getdate(as_on_date) - getdate(row.due_date)).days, 0) if is_overdue else 0,
	}


def get_status(total, paid_amount, installments, as_on_date, precision):
	if flt(paid_amount) - flt(total) > 0.5 * (10**-precision):
		return "Overpaid"
	if not flt(paid_amount):
		return "Overdue" if any(item["status"] == "Overdue" for item in installments) else "Unpaid"
	if flt(paid_amount) >= flt(total) - 0.5 * (10**-precision):
		return "Fully Paid"
	return "Overdue" if any(item["status"] == "Overdue" for item in installments) else "Partially Paid"


def include_summary_row(payment, filters):
	if filters.payment_status and payment["status"] != filters.payment_status:
		return False
	if filters.show_only_pending_payments and not any(
		item["outstanding_amount"] > 0 for item in payment["installments"]
	):
		return False
	if filters.show_only_overdue_payments and not any(
		item["status"] == "Overdue" for item in payment["installments"]
	):
		return False
	if filters.due_date_from or filters.due_date_to:
		return any(
			item["due_date"]
			and (not filters.due_date_from or getdate(item["due_date"]) >= getdate(filters.due_date_from))
			and (not filters.due_date_to or getdate(item["due_date"]) <= getdate(filters.due_date_to))
			for item in payment["installments"]
		)
	return True


def include_installment_row(installment, filters):
	if filters.payment_status and installment["status"] != filters.payment_status:
		return False
	if filters.show_only_pending_payments and installment["outstanding_amount"] <= 0:
		return False
	if filters.show_only_overdue_payments and installment["status"] != "Overdue":
		return False
	if filters.due_date_from and (
		not installment["due_date"] or getdate(installment["due_date"]) < getdate(filters.due_date_from)
	):
		return False
	if filters.due_date_to and (
		not installment["due_date"] or getdate(installment["due_date"]) > getdate(filters.due_date_to)
	):
		return False
	return True


def link_column(label, fieldname, options, width):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Link", "options": options, "width": width}


def data_column(label, fieldname, width):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Data", "width": width}


def currency_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Currency", "width": 130}


def date_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Date", "width": 110}


def int_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Int", "width": 110}


def percent_column(label, fieldname):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Percent", "width": 110}
