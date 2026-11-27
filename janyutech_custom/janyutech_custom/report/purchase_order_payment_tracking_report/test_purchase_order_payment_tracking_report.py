import frappe
from frappe.tests.utils import FrappeTestCase

from janyutech_custom.report.purchase_order_payment_tracking_report.purchase_order_payment_tracking_report import (
	allocate_to_schedule,
	get_status,
)


class TestPurchaseOrderPaymentTrackingReport(FrappeTestCase):
	def test_fifo_allocation_marks_partial_installment_pending(self):
		schedules = [
			frappe._dict(
				{
					"payment_term": "Advance",
					"invoice_portion": 50,
					"due_date": "2026-11-01",
					"payment_amount": 50,
					"idx": 1,
				}
			),
			frappe._dict(
				{
					"payment_term": "Balance",
					"invoice_portion": 50,
					"due_date": "2026-12-01",
					"payment_amount": 50,
					"idx": 2,
				}
			),
		]

		result = allocate_to_schedule(schedules, 25, {}, "2026-11-27")

		self.assertEqual(result[0]["paid_amount"], 25)
		self.assertEqual(result[0]["outstanding_amount"], 25)
		self.assertEqual(result[0]["status"], "Overdue")
		self.assertEqual(result[0]["overdue_days"], 26)
		self.assertEqual(result[1]["paid_amount"], 0)

	def test_no_schedule_does_not_invent_installment(self):
		self.assertEqual(allocate_to_schedule([], 10, {}, "2026-11-27"), [])

	def test_overpaid_status(self):
		self.assertEqual(get_status(100, 101, [], "2026-11-27", 2), "Overpaid")
