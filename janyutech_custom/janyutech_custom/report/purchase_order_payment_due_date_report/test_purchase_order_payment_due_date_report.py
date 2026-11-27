import frappe
from frappe.tests.utils import FrappeTestCase

from janyutech_custom.janyutech_custom.report.purchase_order_payment_due_date_report.purchase_order_payment_due_date_report import (
	classify_due_status,
	due_period_matches,
)


class TestPurchaseOrderPaymentDueDateReport(FrappeTestCase):
	def test_due_status_boundaries(self):
		as_on_date = "2026-11-27"
		self.assertEqual(classify_due_status(frappe._dict(outstanding_amount=10, due_date="2026-11-26"), as_on_date), "Overdue")
		self.assertEqual(classify_due_status(frappe._dict(outstanding_amount=10, due_date=as_on_date), as_on_date), "Due Today")
		self.assertEqual(classify_due_status(frappe._dict(outstanding_amount=10, due_date="2026-11-28"), as_on_date), "Due Tomorrow")
		self.assertEqual(classify_due_status(frappe._dict(outstanding_amount=0, due_date=as_on_date), as_on_date), "Fully Paid")

	def test_due_period_is_relative_to_as_on_date(self):
		row = {"payment_due_status": "Due Within 7 Days", "payment_due_date": "2026-12-03"}
		self.assertTrue(due_period_matches(row, "Next 7 Days", "2026-11-27"))
		self.assertFalse(due_period_matches(row, "Due Today", "2026-11-27"))
